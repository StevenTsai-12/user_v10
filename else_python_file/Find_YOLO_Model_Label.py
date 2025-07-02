import torch

model_path = "C:/Data/code/PycharmProjects/yolov8_practice_v1/best2.pt"
ckpt = torch.load(model_path, map_location='cpu')

if 'model' in ckpt:
    model = ckpt['model']
    if hasattr(model, 'names'):
        print(model.names)
    else:
        print('模型中沒有包含 names 資訊')
else:
    print('不是常見格式的 YOLOv5/v8 .pt 檔案')
