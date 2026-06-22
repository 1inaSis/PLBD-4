/*
 * PLBD-4 HealthGate — Sketch Arduino capteurs biomédicaux (mode commande)
 *
 * Commandes acceptées :
 *   MESURE:temperature  → mesure MLX90614, envoie JSON
 *   MESURE:spo2         → mesure MAX30102 (SpO2 + FC), envoie JSON
 *   MESURE:stop         → annule toute mesure en cours
 *
 * Format de réponse :
 *   {"temperature": 36.7, "source": "capteur"}
 *   {"spo2": 98, "heart_rate": 72, "source": "capteur"}
 *   {"spo2": 98, "heart_rate": null, "source": "partiel"}
 *   {"spo2": null, "heart_rate": null, "source": "erreur"}
 *
 * Bibliothèques requises :
 *   - Adafruit MLX90614 Library
 *   - SparkFun MAX3010x Pulse and Proximity Sensor Library (compatible MAX30102)
 *
 * Câblage I2C (Uno / Nano) : SDA → A4, SCL → A5
 */

#include <Wire.h>
#include <Adafruit_MLX90614.h>
#include <MAX30105.h>
#include "spo2_algorithm.h"

Adafruit_MLX90614 mlx = Adafruit_MLX90614();
MAX30105 capteurMax;

// 50 samples suffisent pour maxim_heart_rate_and_oxygen_saturation — économise 600 bytes RAM
#define TAILLE_BUFFER 50
uint16_t tamponIR[TAILLE_BUFFER];
uint16_t tamponRouge[TAILLE_BUFFER];

// Seuil IR détection doigt (certains modules retournent < 50000)
#define SEUIL_DOIGT 30000UL

bool mlxOk = false;
bool maxOk = false;

// ────────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  Wire.begin();

  for (byte t = 0; t < 3 && !mlxOk; t++) {
    mlxOk = mlx.begin();
    if (!mlxOk) delay(200);
  }
  if (mlxOk) delay(500);

  if (capteurMax.begin(Wire, I2C_SPEED_STANDARD)) {
    maxOk = true;
    capteurMax.setup(0x1F, 4, 2, 100, 411, 4096);
    capteurMax.setPulseAmplitudeRed(0x0A);
  }

  Serial.println(F("[ARDUINO] Pret - en attente de commandes"));
}

// ── Boucle principale ────────────────────────────────────────────────────────
void loop() {
  if (Serial.available() > 0) {
    char commande[25];
    byte len = Serial.readBytesUntil('\n', commande, sizeof(commande) - 1);
    commande[len] = '\0';
    if (len > 0 && commande[len - 1] == '\r') commande[--len] = '\0';

    if (strcmp(commande, "MESURE:temperature") == 0) {
      mesurerTemperature();
    } else if (strcmp(commande, "MESURE:spo2") == 0) {
      mesurerOxymetrie();
    } else if (strcmp(commande, "MESURE:stop") == 0) {
      Serial.println(F("{\"statut\": \"arrete\"}"));
    }
  }
}

// ── Mesure température (MLX90614) ───────────────────────────────────────────
void mesurerTemperature() {
  if (!mlxOk) {
    Serial.println(F("{\"temperature\": null, \"mlx_ok\": false, \"source\": \"erreur\"}"));
    return;
  }

  delay(500);

  const byte NB = 10;
  float vMin = 999.0, vMax = -999.0, somme = 0.0;
  for (byte i = 0; i < NB; i++) {
    float t = mlx.readObjectTempC();
    somme += t;
    if (t < vMin) vMin = t;
    if (t > vMax) vMax = t;
    delay(200);
  }
  float valeur_brute = (somme - vMin - vMax) / (NB - 2);

  if (valeur_brute < 15.0 || valeur_brute > 45.0) {
    Serial.print(F("{\"temperature\": null, \"mlx_ok\": true, \"valeur_brute\": "));
    Serial.print(valeur_brute, 1);
    Serial.println(F(", \"source\": \"erreur\"}"));
    return;
  }

  float temp_finale;
  bool fievre = false;
  if (valeur_brute >= 28.0 && valeur_brute <= 40.0) {
    if (valeur_brute > 37.0) {
      temp_finale = valeur_brute;
      fievre = true;
    } else {
      temp_finale = 36.0 + (valeur_brute - 28.0) / 12.0 * 2.0;
      if (temp_finale < 36.0) temp_finale = 36.0;
      if (temp_finale > 38.0) temp_finale = 38.0;
    }
  } else {
    temp_finale = valeur_brute;
  }

  Serial.print(F("{\"temperature\": "));
  Serial.print(temp_finale, 1);
  Serial.print(F(", \"mlx_ok\": true, \"valeur_brute\": "));
  Serial.print(valeur_brute, 1);
  if (fievre) Serial.print(F(", \"fievre\": true"));
  Serial.println(F(", \"mesure_type\": \"surface_cutanee\", \"source\": \"capteur\"}"));
}

// ── Utilitaire : lit N samples en lots (FIFO max 32 samples) ────────────────
int lireSamples(int taille) {
  int lus = 0;
  unsigned long debut = millis();
  unsigned long timeout = (unsigned long)taille * 20UL + 5000UL;

  while (lus < taille) {
    if (millis() - debut > timeout) break;
    capteurMax.check();
    while (capteurMax.available() && lus < taille) {
      tamponRouge[lus] = capteurMax.getRed();
      tamponIR[lus]    = capteurMax.getIR();
      capteurMax.nextSample();
      lus++;
    }
    if (lus < taille) delay(100);
  }
  return lus;
}

// ── Mesure SpO2 + FC (MAX30102) ──────────────────────────────────────────────
void mesurerOxymetrie() {
  if (!maxOk) {
    Serial.println(F("{\"spo2\": null, \"heart_rate\": null, \"source\": \"erreur\"}"));
    return;
  }

  // Phase 1 : attente doigt (10s)
  unsigned long debut = millis();
  uint32_t irBrut = 0;
  bool doigtDetecte = false;

  while (millis() - debut < 10000UL) {
    capteurMax.check();
    if (capteurMax.available()) {
      irBrut = capteurMax.getIR();
      capteurMax.nextSample();
      if (irBrut > SEUIL_DOIGT) { doigtDetecte = true; break; }
    }
  }

  if (!doigtDetecte) {
    Serial.println(F("{\"spo2\": null, \"heart_rate\": null, \"source\": \"erreur\"}"));
    return;
  }

  // Phase 2 : vider FIFO + stabilisation
  capteurMax.clearFIFO();
  delay(500);

  // Phase 3 : remplissage initial 50 samples
  if (lireSamples(TAILLE_BUFFER) < TAILLE_BUFFER) {
    Serial.println(F("{\"spo2\": null, \"heart_rate\": null, \"source\": \"erreur\"}"));
    return;
  }

  // Phase 4 : 12 itérations de calcul (passes de 50 samples)
  int32_t valeurSpo2     = 0;
  int8_t  spo2Valide     = 0;
  int32_t valeurFreqCard = 0;
  int8_t  freqCardValide = 0;

  for (byte iter = 0; iter < 12; iter++) {
    lireSamples(TAILLE_BUFFER);
    maxim_heart_rate_and_oxygen_saturation(
      tamponIR, TAILLE_BUFFER, tamponRouge,
      &valeurSpo2, &spo2Valide,
      &valeurFreqCard, &freqCardValide
    );
  }

  // Phase 5 : 4 passes supplémentaires de 50 si algorithme échoue (-999)
  for (byte extra = 0; extra < 4 && valeurSpo2 == -999; extra++) {
    lireSamples(TAILLE_BUFFER);
    maxim_heart_rate_and_oxygen_saturation(
      tamponIR, TAILLE_BUFFER, tamponRouge,
      &valeurSpo2, &spo2Valide,
      &valeurFreqCard, &freqCardValide
    );
  }

  bool spo2Ok = spo2Valide     && (valeurSpo2     >= 70) && (valeurSpo2     <= 100);
  bool freqOk = freqCardValide && (valeurFreqCard >= 40) && (valeurFreqCard <= 180);

  if (spo2Ok && freqOk) {
    Serial.print(F("{\"spo2\": "));
    Serial.print(valeurSpo2);
    Serial.print(F(", \"heart_rate\": "));
    Serial.print(valeurFreqCard);
    Serial.println(F(", \"source\": \"capteur\"}"));
  } else if (spo2Ok) {
    // SpO2 fiable, FC hors plage → résultat partiel
    Serial.print(F("{\"spo2\": "));
    Serial.print(valeurSpo2);
    Serial.println(F(", \"heart_rate\": null, \"source\": \"partiel\"}"));
  } else {
    Serial.print(F("{\"spo2\": "));
    Serial.print(valeurSpo2);
    Serial.print(F(", \"heart_rate\": "));
    Serial.print(valeurFreqCard);
    Serial.println(F(", \"source\": \"calibration\"}"));
  }
}
