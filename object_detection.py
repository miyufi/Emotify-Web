import cv2
import numpy as np

MODEL = cv2.dnn.readNet(
    'models/yolov4.weights',
    'models/yolov4.cfg'
)

CLASSES = []
with open("models/coco.names", "r") as f:
    CLASSES = [line.strip() for line in f.readlines()]

OUTPUT_LAYERS = [MODEL.getLayerNames()[i - 1]
                 for i in MODEL.getUnconnectedOutLayers()]
np.random.seed(42)
COLORS = np.random.randint(0, 255, size=(len(CLASSES), 3), dtype="uint8")


def detectObj(snap):
    height = 300
    width = 400
    blob = cv2.dnn.blobFromImage(
        snap, 1/255, (352, 352), swapRB=True, crop=False)

    MODEL.setInput(blob)
    outs = MODEL.forward(OUTPUT_LAYERS)

    class_ids = []
    confidences = []
    boxes = []
    for out in outs:
        for detection in out:
            scores = detection[5:]
            class_id = np.argmax(scores)
            confidence = scores[class_id]
            if confidence > 0.5:
                center_x = int(detection[0]*width)
                center_y = int(detection[1]*height)
                w = int(detection[2]*width)
                h = int(detection[3]*height)

                x = int(center_x - w/2)
                y = int(center_y - h/2)

                boxes.append([x, y, w, h])
                confidences.append(float(confidence))
                class_ids.append(class_id)

    indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)
    for i in range(len(boxes)):
        if i in indexes:
            x, y, w, h = boxes[i]
            label = str(CLASSES[class_ids[i]])
            percentage = "{:.2f}%".format(confidences[0] * 100)
            color = [int(c) for c in COLORS[class_ids[i]]]

    try:
        detectObj.x, detectObj.y, detectObj.w, detectObj.h, detectObj.clr, detectObj.percent, detectObj.lbl = x, y, w, h, color, percentage, label
    except:
        detectObj.lbl = "No label"
