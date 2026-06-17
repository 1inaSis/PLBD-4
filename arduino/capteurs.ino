/*
 * PLBD-4 HealthGate — Sketch Arduino capteurs biomédicaux (mode commande)
 *
 * Mode de fonctionnement :
 *   Le Raspberry Pi envoie une commande série, l'Arduino mesure et répond UNE FOIS,
 *   puis se rendort en attendant la prochaine commande.
 *
 * Commandes acceptées (envoyées par le Pi) :
 *   MESURE:temperature  → mesure MLX90614, envoie JSON, s'arrête
 *   MESURE:spo2         → mesure MAX30102 (SpO2 + FC), envoie JSON, s'arrête
 *   MESURE:stop         → annule toute mesure en cours
 *
 * Format de réponse (toujours sur Serial) :
 *   {"temperature": 36.7, "source": "capteur"}
 *   {"spo2": 98, "heart_rate": 72, "source": "capteur"}
 *   {"temperature": null, "source": "erreur"}   (si capteur absent ou hors plage)
 *
 * Bibliothèques requises :
 *   - Adafruit MLX90614 Library
 *   - SparkFun MAX3010x Pulse and Proximity Sensor Library (compatible MAX30102)
 *
 * Câblage I2C (Uno / Nano) : SDA → A4,  SCL → A5
 */

#include <Wire.h>
#include <Adafruit_MLX90614.h>
#include <MAX30105.h>
#include "spo2_algorithm.h"

// ── Objets capteurs ──────────────────────────────────────────────────────────
Adafruit_MLX90614 mlx = Adafruit_MLX90614();
MAX30105 capteurMax;

// ── Buffer pour l'algorithme SpO2/FC (minimum 25 pour spo2_algorithm) ────────
#define TAILLE_BUFFER 48  // doit correspondre à BUFFER_SIZE dans spo2_algorithm.h (FreqS*4)
uint16_t tamponIR[TAILLE_BUFFER];
uint16_t tamponRouge[TAILLE_BUFFER];

// Seuil IR pour détecter la présence d'un doigt (<50 000 = pas de doigt)
#define SEUIL_DOIGT 50000UL

bool mlxOk = false;
bool maxOk = false;

// ────────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  Wire.begin();

  // Jusqu'à 3 tentatives d'initialisation MLX90614
  for (byte tentative = 0; tentative < 3 && !mlxOk; tentative++) {
    mlxOk = mlx.begin();
    if (!mlxOk) delay(200);
  }
  if (mlxOk) delay(500);  // stabilisation après begin() réussi

  // MAX30102 : 2 LEDs seulement (rouge + infrarouge, pas de verte)
  // ledMode=2 force le mode bicolore compatible MAX30102
  if (capteurMax.begin(Wire, I2C_SPEED_STANDARD)) {
    maxOk = true;
    capteurMax.setup(0x1F, 4, 2, 100, 411, 4096);
    capteurMax.setPulseAmplitudeRed(0x0A);
  }

  Serial.println(F("[ARDUINO] Pret - en attente de commandes"));
}

// ── Boucle principale : attente de commandes ─────────────────────────────────
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
    } else if (strcmp(commande, "SCAN:i2c") == 0) {
      scannerI2C();
    }
  }
}

// ── [DIAG] Scan bus I2C — à supprimer après diagnostic ──────────────────────
void scannerI2C() {
  Serial.print(F("{\"i2c_scan\": ["));
  bool premier = true;
  for (byte addr = 0x00; addr <= 0x7F; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      if (!premier) Serial.print(F(", "));
      Serial.print(F("{\"adresse\": \"0x"));
      if (addr < 0x10) Serial.print(F("0"));
      Serial.print(addr, HEX);
      Serial.print(F("\", \"found\": true}"));
      premier = false;
    }
  }
  Serial.println(F("]}"));
}

// ── Mesure de température (MLX90614) ────────────────────────────────────────
void mesurerTemperature() {
  if (!mlxOk) {
    Serial.println(F("{\"temperature\": null, \"mlx_ok\": false, \"source\": \"erreur\"}"));
    return;
  }

  delay(500);

  float somme = 0.0;
  const byte NB_LECTURES = 5;
  for (byte i = 0; i < NB_LECTURES; i++) {
    somme += mlx.readObjectTempC();
    delay(200);
  }
  float temperature = somme / NB_LECTURES;

  if (temperature < 30.0 || temperature > 45.0) {
    Serial.print(F("{\"temperature\": null, \"mlx_ok\": true, \"valeur_brute\": "));
    Serial.print(temperature, 1);
    Serial.println(F(", \"source\": \"erreur\"}"));
    return;
  }

  Serial.print(F("{\"temperature\": "));
  Serial.print(temperature, 1);
  Serial.println(F(", \"mlx_ok\": true, \"source\": \"capteur\"}"));
}

// ── Mesure SpO2 + fréquence cardiaque (MAX30102) ────────────────────────────
void mesurerOxymetrie() {
  if (!maxOk) {
    Serial.println(F("{\"spo2\": null, \"heart_rate\": null, \"source\": \"erreur\"}"));
    return;
  }

  // Remplissage initial du buffer (25 échantillons ≈ 250 ms à 100 sps)
  for (byte i = 0; i < TAILLE_BUFFER; i++) {
    while (!capteurMax.available()) capteurMax.check();
    tamponRouge[i] = capteurMax.getRed();
    tamponIR[i]    = capteurMax.getIR();
    capteurMax.nextSample();
  }

  if (tamponIR[TAILLE_BUFFER - 1] < SEUIL_DOIGT) {
    Serial.println(F("{\"spo2\": null, \"heart_rate\": null, \"source\": \"erreur\"}"));
    return;
  }

  int32_t valeurSpo2     = 0;
  int8_t  spo2Valide     = 0;
  int32_t valeurFreqCard = 0;
  int8_t  freqCardValide = 0;

  // 4 lectures consécutives de 25 échantillons pour stabilisation
  for (byte iter = 0; iter < 4; iter++) {
    for (byte i = 0; i < TAILLE_BUFFER; i++) {
      while (!capteurMax.available()) capteurMax.check();
      tamponRouge[i] = capteurMax.getRed();
      tamponIR[i]    = capteurMax.getIR();
      capteurMax.nextSample();
    }
    maxim_heart_rate_and_oxygen_saturation(
      tamponIR, TAILLE_BUFFER, tamponRouge,
      &valeurSpo2, &spo2Valide,
      &valeurFreqCard, &freqCardValide
    );
  }

  bool spo2Ok = spo2Valide     && (valeurSpo2     >= 70)  && (valeurSpo2     <= 100);
  bool freqOk = freqCardValide && (valeurFreqCard >= 30)  && (valeurFreqCard <= 220);

  if (!spo2Ok || !freqOk) {
    Serial.println(F("{\"spo2\": null, \"heart_rate\": null, \"source\": \"erreur\"}"));
    return;
  }

  Serial.print(F("{\"spo2\": "));
  Serial.print(valeurSpo2);
  Serial.print(F(", \"heart_rate\": "));
  Serial.print(valeurFreqCard);
  Serial.println(F(", \"source\": \"capteur\"}"));
}
