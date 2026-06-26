/*
 * PLBD-4 HealthGate — Sketch Arduino capteurs biomédicaux (mode commande)
 *
 * Commandes acceptées :
 *   MESURE:temperature  → mesure MLX90614, envoie JSON
 *   MESURE:spo2         → valeurs simulées SpO2 + FC, envoie JSON
 *   MESURE:stop         → annule toute mesure en cours
 *
 * Format de réponse :
 *   {"temperature": 36.7, "source": "capteur"}
 *   {"spo2": 98, "heart_rate": 72, "source": "simulation"}
 *
 * Bibliothèques requises :
 *   - Adafruit MLX90614 Library
 *
 * Câblage I2C (Uno / Nano) : SDA → A4, SCL → A5
 */

#include <Wire.h>
#include <Adafruit_MLX90614.h>

Adafruit_MLX90614 mlx = Adafruit_MLX90614();

bool mlxOk = false;

// ────────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  Wire.begin();

  for (byte t = 0; t < 3 && !mlxOk; t++) {
    mlxOk = mlx.begin();
    if (!mlxOk) delay(200);
  }
  if (mlxOk) delay(500);

  randomSeed(analogRead(0));

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

  if (valeur_brute < 28.0) {
    Serial.print(F("{\"temperature\": null, \"mlx_ok\": true, \"valeur_brute\": "));
    Serial.print(valeur_brute, 1);
    Serial.println(F(", \"source\": \"erreur\"}"));
    return;
  }

  float temp_finale;
  bool fievre = false;
  if (valeur_brute > 45.0) {
    temp_finale = valeur_brute;
    fievre = true;
  } else {
    // 28°C ≤ valeur_brute ≤ 45°C → normalisation vers 36–38°C
    temp_finale = 36.0 + (valeur_brute - 28.0) * (2.0 / 17.0);
    if (temp_finale < 36.0) temp_finale = 36.0;
    if (temp_finale > 38.0) temp_finale = 38.0;
  }

  Serial.print(F("{\"temperature\": "));
  Serial.print(temp_finale, 1);
  Serial.print(F(", \"mlx_ok\": true, \"valeur_brute\": "));
  Serial.print(valeur_brute, 1);
  if (fievre) Serial.print(F(", \"fievre\": true"));
  Serial.println(F(", \"mesure_type\": \"surface_cutanee\", \"source\": \"capteur\"}"));
}

// ── SpO2 + FC simulés (MAX30102 non fiable) ──────────────────────────────────
void mesurerOxymetrie() {
  delay(3000);
  int spo2 = random(96, 100);  // 96–99 %
  int fc   = random(65, 86);   // 65–85 bpm
  Serial.print(F("{\"spo2\": "));
  Serial.print(spo2);
  Serial.print(F(", \"heart_rate\": "));
  Serial.print(fc);
  Serial.println(F(", \"source\": \"simulation\"}"));
}
