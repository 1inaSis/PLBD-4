#include <Wire.h>

void setup() {
  Serial.begin(9600);
  Wire.begin();
  Serial.println("Scan I2C...");
}

void loop() {
  byte count = 0;

  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.print("Trouve : 0x");
      if (addr < 16) Serial.print("0");
      Serial.println(addr, HEX);
      count++;
    }
  }

  if (count == 0)
    Serial.println("Aucun peripherique trouve.");
  else
    Serial.print(count), Serial.println(" peripherique(s) trouve(s).");

  Serial.println("---");
  delay(5000);
}
