import os
import time
import threading
import queue
import cv2
import serial

# Silenciar logs ruidosos de TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import mediapipe.python.solutions.hands as mp_hands
import mediapipe.python.solutions.drawing_utils as mp_draw

# ==================== COLA Y THREAD SERIAL ====================
# Esto garantiza al 100% que la cámara nunca se congele por culpa del puerto COM
serial_queue = queue.Queue(maxsize=1)
SERIAL_PORT = 'COM4'
BAUD_RATE = 9600

def worker_serial():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1, write_timeout=1)
        time.sleep(2)
        print(f"[SERIAL] Conectado exitosamente en {SERIAL_PORT}")
    except Exception as e:
        print(f"[SERIAL ERROR] No se pudo conectar a {SERIAL_PORT}: {e}")
        return

    while True:
        comando = serial_queue.get()
        if comando is None:
            break
        try:
            ser.write(f"{comando}\n".encode('ascii'))
            print(f"[ARDUINO] Comando enviado: {comando}")
        except Exception as e:
            print(f"[SERIAL ERROR] Fallo al escribir: {e}")
        serial_queue.task_done()

# Iniciar hilo de comunicación serial en segundo plano
hilo_serial = threading.Thread(target=worker_serial, daemon=True)
hilo_serial.start()

# ==================== MEDIAPIPE OPTIMIZADO ====================
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    model_complexity=0,              # Complejidad mínima: máxima velocidad en CPU
    min_detection_confidence=0.5,     # Más ligero para no saturar CPU
    min_tracking_confidence=0.5
)

# ==================== CÁMARA (RESOLUCIÓN REDUCIDA) ====================
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)   # Forzar resolución baja
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)

estado_anterior = ""
cooldown = 0
MARGIN = 0.04

GESTO_BUFFER = []
BUFFER_SIZE = 3  # Confirmación rápida en 3 frames

def dedo_extendido(pip, tip):
    return tip.y < pip.y - MARGIN

def detectar_gesto(dedos):
    # dedos = [meñique, índice, anular, medio, pulgar]
    if dedos[1] == 1 and dedos[3] == 1 and dedos[0] == 0 and dedos[2] == 0 and dedos[4] == 0:
        return "PAZ"
    elif dedos[0] == 1 and dedos[1] == 1 and dedos[2] == 1 and dedos[3] == 1 and dedos[4] == 0:
        return "CUATRO_DEDOS"
    elif dedos[1] == 1 and dedos[2] == 1 and dedos[3] == 1 and dedos[0] == 0 and dedos[4] == 0:
        return "TRES_DEDOS"
    elif dedos[1] == 1 and sum(dedos) == 1:
        return "INDICE"
    elif dedos[3] == 1 and sum(dedos) == 1:
        return "MEDIO"
    elif dedos[2] == 1 and sum(dedos) == 1:
        return "ANULAR"
    elif dedos[0] == 1 and sum(dedos) == 1:
        return "MENIQUE"
    elif dedos[4] == 1 and sum(dedos) == 1:
        return "PULGAR"
    elif sum(dedos) == 0:
        return "CERRAR"
    elif sum(dedos) == 5:
        return "ABRIR"
    return None

# ==================== LOOP PRINCIPAL ====================
print("[INFO] Iniciando bucle de video. Presiona ESC en la ventana para salir.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[ERROR] No se pudo leer de la cámara.")
        break

    frame = cv2.flip(frame, 1)
    
    # Optimización de memoria para MediaPipe
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb.flags.writeable = False
    result = hands.process(rgb)
    rgb.flags.writeable = True

    gesto = None

    if result.multi_hand_landmarks:
        hand = result.multi_hand_landmarks[0]
        mp_draw.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

        lm = hand.landmark
        handedness = result.multi_handedness[0].classification[0].label

        dedos = [0, 0, 0, 0, 0]

        # Pulgar
        if handedness == "Right":
            dedos[4] = 1 if lm[4].x < lm[3].x else 0
        else:
            dedos[4] = 1 if lm[4].x > lm[3].x else 0

        # Resto de dedos
        dedos[1] = 1 if dedo_extendido(lm[6], lm[8]) else 0
        dedos[3] = 1 if dedo_extendido(lm[10], lm[12]) else 0
        dedos[2] = 1 if dedo_extendido(lm[14], lm[16]) else 0
        dedos[0] = 1 if dedo_extendido(lm[18], lm[20]) else 0

        gesto_detectado = detectar_gesto(dedos)
        if gesto_detectado:
            GESTO_BUFFER.append(gesto_detectado)
            if len(GESTO_BUFFER) > BUFFER_SIZE:
                GESTO_BUFFER.pop(0)

            if len(GESTO_BUFFER) == BUFFER_SIZE and all(g == GESTO_BUFFER[0] for g in GESTO_BUFFER):
                gesto = GESTO_BUFFER[0]

    # Enviar comando sin bloquear el video (vía Cola)
    if gesto and gesto != estado_anterior and cooldown == 0:
        if serial_queue.empty():
            serial_queue.put(gesto)
        estado_anterior = gesto
        cooldown = 10

    if cooldown > 0:
        cooldown -= 1

    # HUD en pantalla
    texto_display = f"Gesto: {estado_anterior if estado_anterior else 'Esperando...'}"
    cv2.putText(frame, texto_display, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("Control Mano Robotica", frame)
    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()