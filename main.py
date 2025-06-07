from machine import I2C, Pin, ADC
import time
import dht
import urequests
from bmp180 import BMP180
import bme280
import network
import machine

# ===== CPU a 160MHz para mejor rendimiento =====
machine.freq(160000000)

# ==== Configuración del bus I2C ====
i2c = I2C(0, scl=Pin(22), sda=Pin(21))

# ==== Inicialización de sensores ====
bmp = BMP180(i2c)
bme = bme280.BME280(i2c=i2c)

# ==== Configuración MQ-135 ====
mq135 = ADC(Pin(34))  # A0 conectado a GPIO34
mq135.atten(ADC.ATTN_11DB)
mq135.width(ADC.WIDTH_12BIT)

# ==== DHT11 ====
sensor_dht = dht.DHT11(Pin(2))
time.sleep(2)

# ==== Configuración WiFi ====
def conectar_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("🔄 Conectando a WiFi...")
        wlan.connect(ssid, password)
        for _ in range(10):
            if wlan.isconnected():
                break
            print("⏳ Esperando conexión...")
            time.sleep(1)
    if not wlan.isconnected():
        raise RuntimeError("❌ No se pudo conectar a la red Wi-Fi.")
    print("✅ Conectado a Wi-Fi:", wlan.ifconfig())
    return wlan

SSID = "nombre de wifi aqui"
PASSWORD = "contraseña de wifi aqui"
wlan = conectar_wifi(SSID, PASSWORD)

# ==== Configuración ThingSpeak ====
API_KEY = "aqui va la api key que le solicias a thingspeak, debe ser de escritura, no ponemos la nuestra por obvias razones"
TIEMPO_SUBIDA_SEGUNDOS = 120  # 2 minutos

# ==== Funciones auxiliares ====
def leer_mq135():
    try:
        time.sleep(0.2)
        valor = mq135.read()
        voltaje = valor * (3.3 / 4095)
        return valor, voltaje
    except Exception as e:
        print("⚠️ Error al leer MQ135:", e)
        return 0, 0.0

def calidad_aire(volt):
    if volt < 0.4:
        return "Buena 👍"
    elif volt < 0.8:
        return "Moderada 🤔"
    else:
        return "Mala ⚠"

def calcular_sensacion_termica(temp, hum):
    if temp < 27:
        return temp
    T = temp
    H = hum
    HI = (0.5 * (T + 61.0 + ((T - 68.0) * 1.2) + (H * 0.094)))
    return round(HI, 2)

# ==== Loop principal ====
while True:
    print("–––––––––––––––––––––––––––––––")

    # 1. Leer sensores I2C
    try:
        temp_bmp, pres_bmp = bmp.read()
        temp_bme = float(bme.temperature)
        pres_bme = float(bme.pressure)
        print(f"🌡 BMP180 Temp     : {temp_bmp:.2f} °C")
        print(f"📈 BMP180 Presión  : {pres_bmp:.2f} hPa")
        print(f"🌡 BME280 Temp     : {temp_bme:.2f} °C")
        print(f"📈 BME280 Presión  : {pres_bme:.2f} hPa")
    except Exception as e:
        print("❌ Error al leer BMP/BME280:", e)
        temp_bmp, pres_bmp, temp_bme, pres_bme = -1, -1, -1, -1

    promedio_temp = (temp_bmp + temp_bme) / 2 if temp_bmp != -1 and temp_bme != -1 else -1
    promedio_pres = (pres_bmp + pres_bme) / 2 if pres_bmp != -1 and pres_bme != -1 else -1

    # 2. Leer DHT11
    try:
        time.sleep(1)
        sensor_dht.measure()
        temp_dht = sensor_dht.temperature()
        hum_dht = sensor_dht.humidity()
        print(f"🌡 DHT11 Temp     : {temp_dht} °C")
        print(f"💧 DHT11 Humedad  : {hum_dht} %")
    except Exception as e:
        print("❌ Error al leer DHT11:", e)
        temp_dht, hum_dht = -1, -1

    # 3. Leer MQ135
    raw_mq135, mq135_volt = leer_mq135()
    estado = calidad_aire(mq135_volt)
    print(f"📊 MQ135 Crudo     : {raw_mq135}")
    print(f"🔋 MQ135 Voltaje   : {mq135_volt:.2f} V")
    print(f"🌬 Calidad Aire    : {estado}")

    # 4. Sensación térmica
    sensacion_termica = calcular_sensacion_termica(promedio_temp, hum_dht)
    print(f"🌡 Sensación térmica: {sensacion_termica:.2f} °C")

    # 5. Enviar a ThingSpeak
    url = (
        f"http://api.thingspeak.com/update?api_key={API_KEY}"
        f"&field1={promedio_temp:.2f}&field2={promedio_pres:.2f}&field3={hum_dht:.2f}&field4={mq135_volt:.2f}"
        f"&field5={sensacion_termica:.2f}"
    )

    try:
        print("🌐 Enviando datos a ThingSpeak...")
        response = urequests.get(url)
        print("✅ Respuesta del servidor:", response.text)
        response.close()
    except Exception as e:
        print("❌ Error al enviar datos:", e)
        if not wlan.isconnected():
            print("🔄 Reintentando conexión WiFi...")
            wlan = conectar_wifi(SSID, PASSWORD)

    print("–––––––––––––––––––––––––––––––\n")
    time.sleep(TIEMPO_SUBIDA_SEGUNDOS)

