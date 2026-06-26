#解説1
import cv2

#解説2# カメラの設定
cap = cv2.VideoCapture(2) # 0はカメラのデバイス番号

#解説3
# ROIの設定
roi_start_x, roi_start_y = 100, 100 # ROIの左上の座標を設定
roi_width, roi_height = 200, 200 # ROIの幅と高さを設定

#解説4
while True:
    # フレームを読み込む
    ret, frame = cap.read()

    # ROIを抽出
    roi = frame[roi_start_y:roi_start_y+roi_height,
                 roi_start_x:roi_start_x+roi_width]

    # ROIを表示する
    cv2.imshow('ROI', roi)

    # 'q'キーが押されたらループから抜ける
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

#解説5
# キャプチャをリリースしてウィンドウを閉じる
cap.release()
cv2.destroyAllWindows()