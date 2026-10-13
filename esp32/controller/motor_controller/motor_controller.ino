/*
  BrailleTouch — ESP32 Motor Controller + Speaker

  Runs a tiny web server. Each request from the backend includes:
    - "motors": [bool x6]  -> sets the 6 GPIOs directly
    - "character": "a".."z" or "0".."9", or "" -> plays that letter/digit's
      pre-recorded WAV clip through the speaker, if provided

  No Braille logic and no text-to-speech happen on this board — the
  backend already decided both the dot pattern and which letter to speak.
  This board just executes both instructions.

  Board: any standard ESP32 Dev Kit
  Libraries needed: ArduinoJson, ESP8266Audio (works fine on ESP32)
  Requires: LittleFS with a.wav ... z.wav and 0.wav ... 9.wav uploaded
  (see SETUP_GUIDE.md for how to generate and upload these)

  IMPORTANT: motors must be driven through transistor/MOSFET + flyback
  diode circuitry, never straight off a GPIO.
*/

#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include <LittleFS.h>
#include "AudioFileSourceLittleFS.h"
#include "AudioGeneratorWAV.h"
#include "AudioOutputI2S.h"

const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Motor order: dot1, dot2, dot3, dot4, dot5, dot6 (Motor1..Motor6)
const int motorPins[6] = {26, 27, 14, 12, 13, 33};

WebServer server(80);

// Audio out — internal DAC (GPIO25) feeding the PAM8403. GPIO25 is not
// used by any motor above, so there's no pin conflict.
AudioFileSourceLittleFS *audioFile;
AudioGeneratorWAV *wavPlayer;
AudioOutputI2S *audioOut;

void setup() {
  Serial.begin(115200);
  for (int p : motorPins) pinMode(p, OUTPUT);

  if (!LittleFS.begin()) {
    Serial.println("LittleFS mount failed — did you upload the WAV files?");
  }

  audioOut = new AudioOutputI2S(0, AudioOutputI2S::INTERNAL_DAC);
  audioOut->SetOutputModeMono(true);
  audioFile = new AudioFileSourceLittleFS();
  wavPlayer = new AudioGeneratorWAV();

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("Motor controller ready at: " + WiFi.localIP().toString());
  Serial.println("^ copy this IP into backend/config.py as ESP32_CONTROLLER_IP");

  server.on("/motors", HTTP_POST, handleMotors);
  server.begin();
}

void loop() {
  server.handleClient();
  // keep the WAV player running between requests
  if (wavPlayer->isRunning()) {
    if (!wavPlayer->loop()) wavPlayer->stop();
  }
}

void handleMotors() {
  if (!server.hasArg("plain")) {
    server.send(400, "text/plain", "missing body");
    return;
  }

  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, server.arg("plain"));
  if (err) {
    server.send(400, "text/plain", "bad json");
    return;
  }

  JsonArray motors = doc["motors"];
  for (int i = 0; i < 6 && i < (int)motors.size(); i++) {
    digitalWrite(motorPins[i], motors[i].as<bool>() ? HIGH : LOW);
  }

  const char* character = doc["character"] | "";
  if (character && character[0] != '\0') {
    speakCharacter(character[0]);
  }

  server.send(200, "text/plain", "ok");
}

void speakCharacter(char c) {
  String path = "/" + String(c) + ".wav";
  if (!LittleFS.exists(path)) {
    Serial.println("Missing audio file: " + path);
    return;
  }
  if (wavPlayer->isRunning()) wavPlayer->stop();
  audioFile->close();

  bool opened = audioFile->open(path.c_str());
  Serial.println("Opening " + path + ": " + (opened ? "OK" : "FAILED"));
  if (!opened) return;

  bool started = wavPlayer->begin(audioFile, audioOut);
  Serial.println("wavPlayer->begin(): " + String(started ? "OK, playing..." : "FAILED"));
  if (!started) return;

  while (wavPlayer->isRunning()) {
    if (!wavPlayer->loop()) {
      wavPlayer->stop();
      Serial.println("Playback finished.");
    }
  }
}
