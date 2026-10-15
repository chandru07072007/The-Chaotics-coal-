#include <Wire.h>
#include <MPU6050.h>
#include <DHT.h>
#include <math.h>

// =====================================================
// PIN DEFINITIONS
// =====================================================

#define SDA_PIN 21
#define SCL_PIN 22

#define DHT_PIN 4
#define DHT_TYPE DHT11

#define SOIL_PIN 34
#define FSR_PIN 35


// =====================================================
// SENSOR OBJECTS
// =====================================================

MPU6050 mpu;
DHT dht(DHT_PIN, DHT_TYPE);


// =====================================================
// SETUP
// =====================================================

void setup()
{
  Serial.begin(115200);

  // I2C
  Wire.begin(SDA_PIN, SCL_PIN);

  // MPU6050
  mpu.initialize();

  if (mpu.testConnection())
  {
    Serial.println("MPU6050 connected successfully!");
  }
  else
  {
    Serial.println("MPU6050 connection failed!");
  }

  // DHT11
  dht.begin();

  // ESP32 ADC resolution
  analogReadResolution(12);

  Serial.println("--------------------------------");
  Serial.println("     ALL SENSORS INITIALIZED");
  Serial.println("--------------------------------");

  delay(1000);
}


// =====================================================
// LOOP
// =====================================================

void loop()
{
  // ===================================================
  // MPU6050 DATA
  // ===================================================

  int16_t ax, ay, az;
  int16_t gx, gy, gz;

  mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);


  // ===================================================
  // ANGLE X
  // ===================================================

  float angleX = atan2(
    ay,
    sqrt((float)ax * ax + (float)az * az)
  ) * 180.0 / PI;


  // ===================================================
  // ANGLE Y
  // ===================================================

  float angleY = atan2(
    ax,
    sqrt((float)ay * ay + (float)az * az)
  ) * 180.0 / PI;


  // Absolute angle
  float absAngleX = abs(angleX);
  float absAngleY = abs(angleY);


  // ===================================================
  // ANGLE TO PERCENTAGE
  // 0 degree = 0%
  // 45 degree = 100%
  // ===================================================

  float percentageX =
    (absAngleX / 45.0) * 100.0;

  float percentageY =
    (absAngleY / 45.0) * 100.0;

  percentageX = constrain(
    percentageX, 0, 100
  );

  percentageY = constrain(
    percentageY, 0, 100
  );


  // ===================================================
  // VIBRATION CALCULATION
  // ===================================================

  // Convert raw MPU acceleration
  // to acceleration in g.
  //
  // MPU6050 default sensitivity:
  // ±2g = 16384 LSB/g
  //
  // We use this conversion here.

  float accelX = (float)ax / 16384.0;
  float accelY = (float)ay / 16384.0;
  float accelZ = (float)az / 16384.0;


  // Total acceleration in g

  float totalAcceleration =
    sqrt(
      (accelX * accelX) +
      (accelY * accelY) +
      (accelZ * accelZ)
    );


  // Remove gravity

  float vibrationG =
    fabs(totalAcceleration - 1.0);


  // Convert to m/s²

  float vibration =
    vibrationG * 9.81;


  // ===================================================
  // VIBRATION LEVEL
  // Relative 0-100 %
  // ===================================================

  float vibrationLevel =
    (vibration / 10.0) * 100.0;

  vibrationLevel =
    constrain(vibrationLevel, 0, 100);


  // ===================================================
  // DHT11 DATA
  // ===================================================

  float temperature =
    dht.readTemperature();

  float humidity =
    dht.readHumidity();


  // ===================================================
  // SOIL MOISTURE
  // ===================================================

  int soilRaw =
    analogRead(SOIL_PIN);


  // Approximate moisture percentage

  int moisture =
    map(
      soilRaw,
      4095,
      1500,
      0,
      100
    );

  moisture =
    constrain(moisture, 0, 100);


  // ===================================================
  // FSR
  // ===================================================

  int fsrRaw =
    analogRead(FSR_PIN);


  // Approximate force percentage

  int forceLevel =
    map(
      fsrRaw,
      0,
      4095,
      0,
      100
    );

  forceLevel =
    constrain(forceLevel, 0, 100);


  // ===================================================
  // SERIAL OUTPUT
  // ===================================================

  Serial.println();
  Serial.println("======================================");
  Serial.println("            SENSOR DATA");
  Serial.println("======================================");


  // ===================================================
  // MPU6050
  // ===================================================

  Serial.println();
  Serial.println("========== MPU6050 ==========");

  Serial.print("Angle X      : ");
  Serial.print(angleX, 2);
  Serial.println(" deg");

  Serial.print("Angle X      : ");
  Serial.print(percentageX, 1);
  Serial.println(" %");

  Serial.print("Angle Y      : ");
  Serial.print(angleY, 2);
  Serial.println(" deg");

  Serial.print("Angle Y      : ");
  Serial.print(percentageY, 1);
  Serial.println(" %");

  Serial.println();

  Serial.print("Vibration    : ");
  Serial.print(vibration, 2);
  Serial.println(" m/s^2");

  Serial.print("Vibration Level: ");
  Serial.print(vibrationLevel, 1);
  Serial.println(" %");

  Serial.println("==============================");


  // ===================================================
  // DHT11
  // ===================================================

  Serial.println();
  Serial.println("---------- DHT11 ----------");

  if (isnan(temperature) || isnan(humidity))
  {
    Serial.println("DHT11 reading failed!");
  }
  else
  {
    Serial.print("Temperature    : ");
    Serial.print(temperature, 2);
    Serial.println(" °C");

    Serial.print("Humidity       : ");
    Serial.print(humidity, 2);
    Serial.println(" %");
  }


  // ===================================================
  // SOIL MOISTURE
  // ===================================================

  Serial.println();
  Serial.println("------ SOIL MOISTURE ------");

  Serial.print("Raw Value      : ");
  Serial.println(soilRaw);

  Serial.print("Moisture       : ");
  Serial.print(moisture);
  Serial.println(" %");


  // ===================================================
  // FSR
  // ===================================================

  Serial.println();
  Serial.println("----------- FSR -----------");

  Serial.print("Raw Value      : ");
  Serial.println(fsrRaw);

  Serial.print("Force Level    : ");
  Serial.print(forceLevel);
  Serial.println(" %");


  // ===================================================
  // END
  // ===================================================

  Serial.println();
  Serial.println("======================================");

  delay(2000);
}

