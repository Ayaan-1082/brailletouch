/*
  BrailleTouch — ESP32-CAM (remote-triggered capture)

  This board does NOT do OCR/AI. It runs a tiny web server and waits for
  the backend to tell it to capture — no physical button required. When
  triggered, it takes a photo and POSTs the raw JPEG to the backend's
  /api/capture endpoint, same as before.

  Board: AI-Thinker ESP32-CAM
  Tools > Partition Scheme: "Huge APP (3MB No OTA/1MB SPIFFS)"
  Library needed: none extra beyond the esp32 board package
*/

#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <HTTPClient.h>

const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Your backend's address, e.g. "http://192.168.1.40:8000/api/capture"
const char* BACKEND_CAPTURE_URL = "http://192.168.81.111:8000/api/capture";

// AI-Thinker ESP32-CAM pin map
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

WebServer server(80);

void setup() {
  Serial.begin(115200);

  if (!initCamera()) {
    Serial.println("Camera init failed — check wiring/power.");
  }

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected: " + WiFi.localIP().toString());
  Serial.println("^ copy this IP into backend/config.py as ESP32_CAMERA_IP");

  server.on("/capture", HTTP_POST, handleCaptureRequest);
  server.on("/capture", HTTP_GET, handleCaptureRequest); // GET too, easier to test in a browser
  server.begin();
}

void loop() {
  server.handleClient();
}

void handleCaptureRequest() {
  Serial.println("Remote capture triggered by backend.");
  bool ok = captureAndUpload();
  if (ok) {
    server.send(200, "text/plain", "captured and uploaded");
  } else {
    server.send(500, "text/plain", "capture or upload failed");
  }
}

bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_SVGA; // 800x600 — good balance for OCR legibility vs upload size
  config.jpeg_quality = 12;
  config.fb_count = 1;

  return esp_camera_init(&config) == ESP_OK;
}

bool captureAndUpload() {
  Serial.println("Capturing...");
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Capture failed.");
    return false;
  }

  HTTPClient http;
  http.begin(BACKEND_CAPTURE_URL);
  http.addHeader("Content-Type", "image/jpeg");
  http.setTimeout(20000); // 20s — real OCR + AI calls can take longer than the ESP32 HTTPClient's ~5s default
  int code = http.POST(fb->buf, fb->len);
  Serial.println("Upload response code: " + String(code));
  http.end();

  esp_camera_fb_return(fb);
  return code == 200;
}
