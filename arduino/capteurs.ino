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
 *   - SparkFun MAX3010x Pulse and Proximity Sensor Library
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

// ── Buffer pour l'algorithme SpO2/FC ────────────────────────────────────────
#define TAILLE_BUFFER 100
uint32_t tamponIR[TAILLE_BUFFER];
uint32_t tamponRouge[TAILLE_BUFFER];

int32_t valeurSpo2     = 0;
int8_t  spo2Valide     = 0;
int32_t valeurFreqCard = 0;
int8_t  freqCardValide = 0;

// Seuil IR pour détecter la présence d'un doigt (<50 000 = pas de doigt)
const uint32_t SEUIL_DOIGT = 50000;

bool mlxOk = false;
bool maxOk = false;

// ────────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  Wire.begin();

  mlxOk = mlx.begin();

  if (capteurMax.begin(Wire, I2C_SPEED_STANDARD)) {
    maxOk = true;
    capteurMax.setup();
    capteurMax.setPulseAmplitudeRed(0x0A);
    capteurMax.setPulseAmplitudeGreen(0);
  }

  // Signal de démarrage pour la détection automatique du port côté Python
  Serial.println(F("[ARDUINO] Pret - en attente de commandes"));
}

// ── Boucle principale : attente de commandes ─────────────────────────────────
void loop() {
  if (Serial.available() > 0) {
    String commande = Serial.readStringUntil('\n');
    commande.trim();

    if (commande == F("MESURE:temperature")) {
      mesurerTemperature();
    } else if (commande == F("MESURE:spo2")) {
      mesurerOxymetrie();
    } else if (commande == F("MESURE:stop")) {
      Serial.println(F("{\"statut\": \"arrete\"}"));
    }
    // Les commandes inconnues sont ignorées silencieusement
  }
}

// ── Mesure de température (MLX90614) ────────────────────────────────────────
void mesurerTemperature() {
  if (!mlxOk) {
    Serial.println(F("{\"temperature\": null, \"source\": \"erreur\"}"));
    return;
  }

  // Attente courte pour laisser le capteur se stabiliser
  delay(500);

  // Moyenne sur 5 lectures (intervalle 200 ms = 1 s total)
  float somme = 0.0;
  const int NB_LECTURES = 5;
  for (int i = 0; i < NB_LECTURES; i++) {
    somme += mlx.readObjectTempC();
    delay(200);
  }
  float temperature = somme / NB_LECTURES;

  // Validation plage physiologique humaine : 30 °C – 45 °C
  if (temperature < 30.0 || temperature > 45.0) {
    Serial.println(F("{\"temperature\": null, \"source\": \"erreur\"}"));
    return;
  }

  Serial.print(F("{\"temperature\": "));
  Serial.print(temperature, 1);
  Serial.println(F(", \"source\": \"capteur\"}"));
}

// ── Mesure SpO2 + fréquence cardiaque (MAX30102) ────────────────────────────
void mesurerOxymetrie() {
  if (!maxOk) {
    Serial.println(F("{\"spo2\": null, \"heart_rate\": null, \"source\": \"erreur\"}"));
    return;
  }

  // Remplissage initial du buffer (100 échantillons ≈ 1 s à 100 sps)
  for (byte i = 0; i < TAILLE_BUFFER; i++) {
    while (!capteurMax.available()) capteurMax.check();
    tamponRouge[i] = capteurMax.getRed();
    tamponIR[i]    = capteurMax.getIR();
    capteurMax.nextSample();
  }

  // Vérifier que le doigt est posé sur le capteur
  if (tamponIR[TAILLE_BUFFER - 1] < SEUIL_DOIGT) {
    Serial.println(F("{\"spo2\": null, \"heart_rate\": null, \"source\": \"erreur\"}"));
    return;
  }

  // 4 itérations de fenêtre glissante pour stabilisation (~4 s supplémentaires)
  for (int iter = 0; iter < 4; iter++) {
    // Décaler les anciens échantillons
    for (byte i = 25; i < TAILLE_BUFFER; i++) {
      tamponRouge[i - 25] = tamponRouge[i];
      tamponIR[i - 25]    = tamponIR[i];
    }
    // Lire 25 nouveaux échantillons (~250 ms)
    for (byte i = TAILLE_BUFFER - 25; i < TAILLE_BUFFER; i++) {
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

  // Validation des plages physiologiques
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
