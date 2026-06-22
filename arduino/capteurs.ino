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

// ── Buffers pour l'algorithme SpO2/FC ────────────────────────────────────────
#define TAILLE_BUFFER       100  // mesure normale
#define TAILLE_BUFFER_GRAND 200  // retry si spo2 == -999 (FIFO corrompu)
// Alloué à la taille max pour éviter un second malloc sur l'Arduino
uint16_t tamponIR[TAILLE_BUFFER_GRAND];
uint16_t tamponRouge[TAILLE_BUFFER_GRAND];

// Seuil IR pour détecter la présence d'un doigt
// Certains modules MAX30102 retournent des valeurs plus faibles → 30000
#define SEUIL_DOIGT 30000UL

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
    Serial.println(F("[MAX30102] begin() OK - capteur initialise"));
  } else {
    Serial.println(F("[MAX30102] begin() ECHEC - capteur non detecte"));
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
    }
  }
}

// ── Mesure de température (MLX90614) ────────────────────────────────────────
void mesurerTemperature() {
  if (!mlxOk) {
    Serial.println(F("{\"temperature\": null, \"mlx_ok\": false, \"source\": \"erreur\"}"));
    return;
  }

  delay(500);

  // 10 lectures, suppression min+max, moyenne des 8 restantes
  const byte NB = 10;
  float lectures[NB];
  for (byte i = 0; i < NB; i++) {
    lectures[i] = mlx.readObjectTempC();
    delay(200);
  }
  float vMin = lectures[0], vMax = lectures[0];
  float somme = 0.0;
  for (byte i = 0; i < NB; i++) {
    somme += lectures[i];
    if (lectures[i] < vMin) vMin = lectures[i];
    if (lectures[i] > vMax) vMax = lectures[i];
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
      // Fièvre réelle détectable : ne pas normaliser pour préserver le signal clinique
      temp_finale = valeur_brute;
      fievre = true;
    } else {
      // Zone corporelle normale : normalisation vers 36.0–38.0°C
      temp_finale = 36.0 + (valeur_brute - 28.0) / 12.0 * 2.0;
      if (temp_finale < 36.0) temp_finale = 36.0;
      if (temp_finale > 38.0) temp_finale = 38.0;
    }
  } else {
    // Hors zone corporelle (eau chaude/froide, test matériel) : brute directe
    temp_finale = valeur_brute;
  }

  Serial.print(F("{\"temperature\": "));
  Serial.print(temp_finale, 1);
  Serial.print(F(", \"mlx_ok\": true, \"valeur_brute\": "));
  Serial.print(valeur_brute, 1);
  if (fievre) {
    Serial.print(F(", \"fievre\": true"));
  }
  Serial.println(F(", \"mesure_type\": \"surface_cutanee\", \"source\": \"capteur\"}"));
}

// ── Utilitaire : lit N samples dans les tampons globaux ──────────────────────
void lireSamples(int taille) {
  for (int i = 0; i < taille; i++) {
    unsigned long t = millis();
    while (!capteurMax.available()) {
      capteurMax.check();
      if (millis() - t > 2000UL) break;
    }
    tamponRouge[i] = capteurMax.getRed();
    tamponIR[i]    = capteurMax.getIR();
    capteurMax.nextSample();
  }
}

// ── Mesure SpO2 + fréquence cardiaque (MAX30102) ────────────────────────────
void mesurerOxymetrie() {
  if (!maxOk) {
    Serial.println(F("{\"spo2\": null, \"heart_rate\": null, \"max_ok\": false, \"source\": \"erreur\"}"));
    return;
  }

  Serial.println(F("[MAX30102] Debut mesure (10s) - poser le doigt"));

  // ── Phase 1 : attente détection doigt (jusqu'à 10s) ────────────────────────
  unsigned long debut = millis();
  uint32_t irBrut = 0, rougeBrut = 0;
  bool doigtDetecte = false;

  while (millis() - debut < 10000UL) {
    capteurMax.check();
    if (capteurMax.available()) {
      irBrut    = capteurMax.getIR();
      rougeBrut = capteurMax.getRed();
      capteurMax.nextSample();

      if (irBrut > SEUIL_DOIGT) {
        doigtDetecte = true;
        Serial.print(F("[MAX30102] Doigt detecte - IR="));
        Serial.print(irBrut);
        Serial.print(F(" Rouge="));
        Serial.println(rougeBrut);
        break;
      }
    }
  }

  if (!doigtDetecte) {
    Serial.print(F("[MAX30102] Pas de doigt apres 10s - IR brut="));
    Serial.print(irBrut);
    Serial.print(F(" (seuil="));
    Serial.print(SEUIL_DOIGT);
    Serial.println(F(")"));
    Serial.print(F("{\"spo2\": null, \"heart_rate\": null, \"ir_brut\": "));
    Serial.print(irBrut);
    Serial.print(F(", \"rouge_brut\": "));
    Serial.print(rougeBrut);
    Serial.print(F(", \"seuil_doigt\": "));
    Serial.print(SEUIL_DOIGT);
    Serial.println(F(", \"source\": \"erreur\"}"));
    return;
  }

  // ── Phase 2 : vider le FIFO (données corrompues avant la détection) ─────────
  capteurMax.clearFIFO();
  Serial.println(F("[MAX30102] FIFO vide - attente 500ms"));
  delay(500);

  // ── Phase 3 : remplissage buffer 100 samples + logs ─────────────────────────
  Serial.println(F("[MAX30102] Remplissage buffer 100 samples..."));
  lireSamples(TAILLE_BUFFER);
  Serial.print(F("[MAX30102] IR[0]="));
  Serial.print(tamponIR[0]);
  Serial.print(F(" Rouge[0]="));
  Serial.print(tamponRouge[0]);
  Serial.print(F(" IR[99]="));
  Serial.print(tamponIR[TAILLE_BUFFER - 1]);
  Serial.print(F(" Rouge[99]="));
  Serial.println(tamponRouge[TAILLE_BUFFER - 1]);

  // ── Phase 4 : calcul SpO2/FC — 8 itérations pour stabilisation ──────────────
  int32_t valeurSpo2     = 0;
  int8_t  spo2Valide     = 0;
  int32_t valeurFreqCard = 0;
  int8_t  freqCardValide = 0;

  for (byte iter = 0; iter < 8; iter++) {
    lireSamples(TAILLE_BUFFER);
    maxim_heart_rate_and_oxygen_saturation(
      tamponIR, TAILLE_BUFFER, tamponRouge,
      &valeurSpo2, &spo2Valide,
      &valeurFreqCard, &freqCardValide
    );
    Serial.print(F("[MAX30102] iter="));
    Serial.print(iter);
    Serial.print(F(" spo2="));
    Serial.print(valeurSpo2);
    Serial.print(F(" valide="));
    Serial.print(spo2Valide);
    Serial.print(F(" fc="));
    Serial.print(valeurFreqCard);
    Serial.print(F(" valide="));
    Serial.println(freqCardValide);
  }

  // ── Phase 5 : retry 200 samples si algorithme renvoie -999 ──────────────────
  if (valeurSpo2 == -999) {
    Serial.println(F("[MAX30102] spo2=-999 -> retry 200 samples"));
    lireSamples(TAILLE_BUFFER_GRAND);
    maxim_heart_rate_and_oxygen_saturation(
      tamponIR, TAILLE_BUFFER_GRAND, tamponRouge,
      &valeurSpo2, &spo2Valide,
      &valeurFreqCard, &freqCardValide
    );
    Serial.print(F("[MAX30102] retry spo2="));
    Serial.print(valeurSpo2);
    Serial.print(F(" valide="));
    Serial.print(spo2Valide);
    Serial.print(F(" fc="));
    Serial.print(valeurFreqCard);
    Serial.print(F(" valide="));
    Serial.println(freqCardValide);
  }

  bool spo2Ok = spo2Valide     && (valeurSpo2     >= 70)  && (valeurSpo2     <= 100);
  bool freqOk = freqCardValide && (valeurFreqCard >= 40)  && (valeurFreqCard <= 200);

  if (spo2Ok && freqOk) {
    Serial.print(F("{\"spo2\": "));
    Serial.print(valeurSpo2);
    Serial.print(F(", \"heart_rate\": "));
    Serial.print(valeurFreqCard);
    Serial.println(F(", \"source\": \"capteur\"}"));
  } else {
    Serial.print(F("[MAX30102] Non valide - spo2_valide="));
    Serial.print(spo2Valide);
    Serial.print(F(" fc_valide="));
    Serial.println(freqCardValide);
    Serial.print(F("{\"spo2\": "));
    Serial.print(valeurSpo2);
    Serial.print(F(", \"heart_rate\": "));
    Serial.print(valeurFreqCard);
    Serial.print(F(", \"spo2_valide\": "));
    Serial.print(spo2Valide);
    Serial.print(F(", \"fc_valide\": "));
    Serial.print(freqCardValide);
    Serial.println(F(", \"source\": \"calibration\"}"));
  }
}
