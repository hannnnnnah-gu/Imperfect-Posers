"""
Hannah Gu
July 14, 2026
Imperfect Posers: A photobooth style mimicking game!!
Updated with save1.png/save2.png image buttons & aspect-ratio stretch fix!
"""

import cv2
import numpy as np
import os
import time
import math
import random

# AI pose recognition
try:
    import mediapipe as mp
except ImportError:
    print("Mediapipe not found. Run: python3 -m pip install \"mediapipe<=0.10.14\" --force-reinstall")
    exit()

mp_pose = mp.solutions.pose
pose_tracker = mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.5)

def get_landmark_angles(image):
    """ Identifies key angles of the body that make up the base pose """
    if image is None:
        return None
    rgb_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = pose_tracker.process(rgb_img)
    
    if not results.pose_landmarks:
        return None
        
    landmarks = results.pose_landmarks.landmark
    
    def calculate_angle(a, b, c):
        ang = math.degrees(math.atan2(c.y-b.y, c.x-b.x) - math.atan2(a.y-b.y, a.x-b.x))
        return abs(ang) if abs(ang) <= 180 else 360 - abs(ang)

    try:
        l_elbow = calculate_angle(landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER],
                                  landmarks[mp_pose.PoseLandmark.LEFT_ELBOW],
                                  landmarks[mp_pose.PoseLandmark.LEFT_WRIST])
        r_elbow = calculate_angle(landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER],
                                  landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW],
                                  landmarks[mp_pose.PoseLandmark.RIGHT_WRIST])
        return [l_elbow, r_elbow]
    except Exception:
        return None

def crop_to_aspect_ratio(frame, target_w, target_h):
    """Crops the center of the frame to match the target aspect ratio perfectly, preventing stretching."""
    if frame is None or frame.size == 0:
        return np.ones((target_h, target_w, 3), dtype=np.uint8) * 100
        
    h, w = frame.shape[:2]
    target_aspect = target_w / target_h
    current_aspect = w / h
    
    if current_aspect > target_aspect:
        # Frame is too wide. Crop the sides.
        new_w = int(h * target_aspect)
        offset = (w - new_w) // 2
        return frame[:, offset:offset+new_w]
    elif current_aspect < target_aspect:
        # Frame is too tall. Crop the top and bottom.
        new_h = int(w / target_aspect)
        offset = (h - new_h) // 2
        return frame[offset:offset+new_h, :]
    return frame

# File locator
HOME = os.path.expanduser("~")
POSSIBLE_PATHS = [
    os.path.join(HOME, "Desktop", "HackTheArts"),
    os.path.join(HOME, "Documents", "HackTheArts"),
    os.path.join(HOME, "Downloads", "HackTheArts")
]

TARGET_DIR = next((p for p in POSSIBLE_PATHS if os.path.exists(p)), os.getcwd())
print(f" Finding target images from: {TARGET_DIR}")

# Custom helper function to blend PNG transparency overlays cleanly
def overlay_png(background, overlay, x, y):
    if overlay is None: return
    h, w = overlay.shape[:2]
    bg_h, bg_w = background.shape[:2]
    
    if x >= bg_w or y >= bg_h or x + w <= 0 or y + h <= 0:
        return
        
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(bg_w, x + w), min(bg_h, y + h)
    
    overlay_x1 = x1 - x
    overlay_y1 = y1 - y
    overlay_x2 = overlay_x1 + (x2 - x1)
    overlay_y2 = overlay_y1 + (y2 - y1)
    
    sub_overlay = overlay[overlay_y1:overlay_y2, overlay_x1:overlay_x2]
    
    if sub_overlay.shape[2] == 4:
        alpha = (sub_overlay[:, :, 3] / 255.0)[:, :, np.newaxis]
        background[y1:y2, x1:x2] = (1.0 - alpha) * background[y1:y2, x1:x2] + alpha * sub_overlay[:, :, :3]
    else:
        background[y1:y2, x1:x2] = sub_overlay[:, :, :3]

# --- LOAD STICKER ASSETS ---
sticker_files = {
    "pink": ["pink_star.png", "pink_star.jpg"],
    "purple": ["purple_star.png", "purple_star.jpg"],
    "teal": ["teal_star.png", "teal_star.jpg"],
    "yellow": ["yellow_star.png", "yellow_star.jpg"]
}
stickers = {}
for key, files in sticker_files.items():
    stk_path = next((os.path.join(TARGET_DIR, f) for f in files if os.path.exists(os.path.join(TARGET_DIR, f))), None)
    if stk_path:
        img = cv2.imread(stk_path, cv2.IMREAD_UNCHANGED)
        if img is not None:
            stickers[key] = cv2.resize(img, (45, 45))

def create_fallback_star(bgr_color):
    img = np.zeros((45, 45, 4), dtype=np.uint8)
    cv2.circle(img, (22, 22), 18, (*bgr_color, 255), -1)
    cv2.circle(img, (22, 22), 18, (255, 255, 255, 255), 2)
    cv2.putText(img, "*", (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255, 255), 2)
    return img

if "pink" not in stickers: stickers["pink"] = create_fallback_star((203, 192, 255))
if "purple" not in stickers: stickers["purple"] = create_fallback_star((211, 0, 148))
if "teal" not in stickers: stickers["teal"] = create_fallback_star((208, 224, 64))
if "yellow" not in stickers: stickers["yellow"] = create_fallback_star((0, 215, 255))

# --- START SCREEN SYSTEM ---
start_screen_active = True
info_screen_active = False
button_state = 1        
info_button_state = 1   
mouse_clicked = False

bg_path = next((os.path.join(TARGET_DIR, f) for f in ["background.jpg", "background.png"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)
logo_path = next((os.path.join(TARGET_DIR, f) for f in ["logo.jpg", "logo.png"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)
start1_path = next((os.path.join(TARGET_DIR, f) for f in ["start1.jpg", "start1.png"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)
start2_path = next((os.path.join(TARGET_DIR, f) for f in ["start2.jpg", "start2.png"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)

info1_path = next((os.path.join(TARGET_DIR, f) for f in ["info1.jpg", "info1.png", "info.jpg", "info.png"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)
info2_path = next((os.path.join(TARGET_DIR, f) for f in ["info2.jpg", "info2.png"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)
infobg_path = next((os.path.join(TARGET_DIR, f) for f in ["info_bg.png", "info_bg.jpg"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)

again1_path = next((os.path.join(TARGET_DIR, f) for f in ["again1.png", "again1.jpg", "again1.PNG"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)
again2_path = next((os.path.join(TARGET_DIR, f) for f in ["again2.png", "again2.jpg", "again2.PNG"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)

save1_path = next((os.path.join(TARGET_DIR, f) for f in ["save1.png", "save1.jpg", "save1.PNG"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)
save2_path = next((os.path.join(TARGET_DIR, f) for f in ["save2.png", "save2.jpg", "save2.PNG"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)

# New paths for NEXT and CLEAR buttons
next1_path = next((os.path.join(TARGET_DIR, f) for f in ["next1.png", "next1.jpg", "next1.PNG"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)
next2_path = next((os.path.join(TARGET_DIR, f) for f in ["next2.png", "next2.jpg", "next2.PNG"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)
clear_path = next((os.path.join(TARGET_DIR, f) for f in ["clear.png", "clear.jpg", "clear.PNG"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)

start_btn_path = next((os.path.join(TARGET_DIR, f) for f in ["start.jpg", "start.png"] if os.path.exists(os.path.join(TARGET_DIR, f))), None)

bg_img = cv2.imread(bg_path) if bg_path else np.ones((600, 800, 3), dtype=np.uint8) * 45
if bg_img is None: bg_img = np.ones((600, 800, 3), dtype=np.uint8) * 45
bg_img = cv2.resize(bg_img, (800, 600))

infobg_img = cv2.imread(infobg_path) if infobg_path else None
if infobg_img is not None:
    infobg_img = cv2.resize(infobg_img, (800, 600))
else:
    infobg_img = np.ones((600, 800, 3), dtype=np.uint8) * 60
    cv2.putText(infobg_img, "info_bg.png Missing! Press SPACE to go back.", (100, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

logo_img = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED) if logo_path else None
btn1 = cv2.imread(start2_path, cv2.IMREAD_UNCHANGED) if start2_path else None
btn2 = cv2.imread(start1_path, cv2.IMREAD_UNCHANGED) if start1_path else None

infobtn1 = cv2.imread(info1_path, cv2.IMREAD_UNCHANGED) if info1_path else None
infobtn2 = cv2.imread(info2_path, cv2.IMREAD_UNCHANGED) if info2_path else None

againbtn1 = cv2.imread(again1_path, cv2.IMREAD_UNCHANGED) if again1_path else None
againbtn2 = cv2.imread(again2_path, cv2.IMREAD_UNCHANGED) if again2_path else None

savebtn1 = cv2.imread(save1_path, cv2.IMREAD_UNCHANGED) if save1_path else None
savebtn2 = cv2.imread(save2_path, cv2.IMREAD_UNCHANGED) if save2_path else None

nextbtn1 = cv2.imread(next1_path, cv2.IMREAD_UNCHANGED) if next1_path else None
nextbtn2 = cv2.imread(next2_path, cv2.IMREAD_UNCHANGED) if next2_path else None
clearbtn_img = cv2.imread(clear_path, cv2.IMREAD_UNCHANGED) if clear_path else None

start_btn_img = cv2.imread(start_btn_path, cv2.IMREAD_UNCHANGED) if start_btn_path else None

game_logo_img = None
if logo_img is not None:
    game_logo_img = cv2.resize(logo_img, (450, 215))
    logo_img = cv2.resize(logo_img, (720, 340))
if btn1 is not None: btn1 = cv2.resize(btn1, (200, 80))
if btn2 is not None: btn2 = cv2.resize(btn2, (200, 80))
if infobtn1 is not None: infobtn1 = cv2.resize(infobtn1, (180, 72))
if infobtn2 is not None: infobtn2 = cv2.resize(infobtn2, (180, 72))
if againbtn1 is not None: againbtn1 = cv2.resize(againbtn1, (220, 60))
if againbtn2 is not None: againbtn2 = cv2.resize(againbtn2, (220, 60))
if savebtn1 is not None: savebtn1 = cv2.resize(savebtn1, (120, 60))
if savebtn2 is not None: savebtn2 = cv2.resize(savebtn2, (120, 60))

if nextbtn1 is not None: nextbtn1 = cv2.resize(nextbtn1, (120, 55))
if nextbtn2 is not None: nextbtn2 = cv2.resize(nextbtn2, (120, 55))
if clearbtn_img is not None: clearbtn_img = cv2.resize(clearbtn_img, (140, 60))

if start_btn_img is not None: start_btn_img = cv2.resize(start_btn_img, (400, 60))

logo_x, logo_y = (800 - 750) // 2, 40
btn_x, btn_y = (800 - 200) // 2, 390     
info_x, info_y = (800 - 180) // 2, 490   

def handle_mouse(event, x, y, flags, param):
    global button_state, info_button_state, mouse_clicked, start_screen_active, info_screen_active
    
    if info_screen_active:
        return

    if btn_x <= x <= btn_x + 200 and btn_y <= y <= btn_y + 80:
        info_button_state = 1
        if event == cv2.EVENT_LBUTTONDOWN:
            button_state = 2
            mouse_clicked = True
        elif event == cv2.EVENT_LBUTTONUP and mouse_clicked:
            start_screen_active = False
        else:
            button_state = 2
            
    elif info_x <= x <= info_x + 200 and info_y <= y <= info_y + 80:
        button_state = 1
        if event == cv2.EVENT_LBUTTONDOWN:
            info_button_state = 2
            mouse_clicked = True
        elif event == cv2.EVENT_LBUTTONUP and mouse_clicked:
            info_screen_active = True
        else:
            info_button_state = 2
    else:
        button_state = 1
        info_button_state = 1
        mouse_clicked = False

cv2.namedWindow("Imperfect Posers", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("Imperfect Posers", handle_mouse)

# Start Screen Loop
while start_screen_active:
    if info_screen_active:
        menu_frame = infobg_img.copy()
    else:
        menu_frame = bg_img.copy()
        if logo_img is not None:
            overlay_png(menu_frame, logo_img, logo_x, logo_y)
        else:
            cv2.putText(menu_frame, "IMPERFECT POSERS", (120, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (255, 255, 255), 4)

        active_btn = btn2 if button_state == 2 and btn2 is not None else btn1
        if active_btn is not None:
            overlay_png(menu_frame, active_btn, btn_x, btn_y)
        else:
            color = (0, 0, 255) if button_state == 2 else (0, 255, 0)
            cv2.rectangle(menu_frame, (btn_x, btn_y), (btn_x + 200, btn_y + 80), color, -1)
            cv2.putText(menu_frame, "START", (btn_x + 50, btn_y + 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        active_info_btn = infobtn2 if info_button_state == 2 and infobtn2 is not None else infobtn1
        if active_info_btn is not None:
            overlay_png(menu_frame, active_info_btn, info_x, info_y)
        else:
            color = (0, 0, 255) if info_button_state == 2 else (0, 255, 255)
            cv2.rectangle(menu_frame, (info_x, info_y), (info_x + 200, info_y + 80), color, -1)
            cv2.putText(menu_frame, "INFO", (info_x + 60, info_y + 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    cv2.imshow("Imperfect Posers", menu_frame)
    
    key = cv2.waitKey(30)
    if key == 27:
        cv2.destroyAllWindows()
        exit()
    elif info_screen_active and key & 0xFF == 32: 
        info_screen_active = False

cv2.setMouseCallback("Imperfect Posers", lambda *args: None)
cv2.destroyAllWindows()


# --- HELPER TO DRAW PHOTOSTRIP (CLEAN, NO AI SCORES) ---
def build_photostrip(frames, bg_color_bgr, placed_stickers):
    """ Builds a clean vertical photostrip with white/color frame and star stickers """
    photo_w, photo_h = 300, 170
    margin_x = 30
    margin_top = 50
    inter_gap = 15
    margin_bottom = 60
    
    strip_w = photo_w + (margin_x * 2)  # 360 px
    strip_h = margin_top + (4 * photo_h) + (3 * inter_gap) + margin_bottom # 885 px
    
    strip = np.zeros((strip_h, strip_w, 3), dtype=np.uint8)
    strip[:] = bg_color_bgr
    
    luminance = sum(bg_color_bgr) / 3
    txt_color = (40, 40, 40) if luminance > 128 else (245, 245, 245)
    
    cv2.putText(strip, "IMPERFECT POSERS", (margin_x + 20, 35), cv2.FONT_HERSHEY_TRIPLEX, 0.65, txt_color, 1)
    
    for i, img in enumerate(frames):
        y_pos = margin_top + i * (photo_h + inter_gap)
        x_pos = margin_x
        
        # Crop before resize to prevent horizontal stretching
        cropped = crop_to_aspect_ratio(img, photo_w, photo_h)
        resized = cv2.resize(cropped, (photo_w, photo_h))
        
        cv2.rectangle(strip, (x_pos - 2, y_pos - 2), (x_pos + photo_w + 2, y_pos + photo_h + 2), (210, 210, 210), 1)
        strip[y_pos:y_pos+photo_h, x_pos:x_pos+photo_w] = resized
            
    for key, cx, cy in placed_stickers:
        stk = stickers.get(key)
        if stk is not None:
            sh, sw = stk.shape[:2]
            overlay_png(strip, stk, cx - sw // 2, cy - sh // 2)
            
    return strip


# --- MAIN REPLAY LOOP ---
cap = cv2.VideoCapture(0)
game_running = True

while game_running:
    base_names = ["target1", "target2", "target4", "target5", "target7"]
    base_names = random.sample(base_names, 4)
    targets = []
    target_angles = []

    print("Target poses are being analysed by AI..")
    for name in base_names:
        possible_files = [f"{name}.png", f"{name}.jpg", f"{name}.PNG", f"{name}.jpg.png", f"{name}.png.jpg", f"{name}.png.jpeg"]
        img = None
        for file in possible_files:
            full_path = os.path.join(TARGET_DIR, file)
            if os.path.exists(full_path):
                img = cv2.imread(full_path)
                if img is not None: break
                    
        if img is None:
            img = np.ones((400, 300, 3), dtype=np.uint8) * 100
            cv2.putText(img, f"Missing: {name}", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        name_alt = f"{name}-5"
        possible_alt_files = [f"{name_alt}.png", f"{name_alt}.jpg", f"{name_alt}.PNG", f"{name_alt}.jpg.png", f"{name_alt}.png.jpg", f"{name_alt}.png.jpeg"]
        img_alt = None
        for file in possible_alt_files:
            full_path = os.path.join(TARGET_DIR, file)
            if os.path.exists(full_path):
                img_alt = cv2.imread(full_path)
                if img_alt is not None: break
                    
        if img_alt is None: img_alt = img.copy()

        name_human = f"{name}_human"
        possible_human_files = [f"{name_human}.png", f"{name_human}.jpg", f"{name_human}.PNG", f"{name_human}.jpg.png", f"{name_human}.png.jpg", f"{name_human}.png.jpeg"]
        img_human = None
        for file in possible_human_files:
            full_path = os.path.join(TARGET_DIR, file)
            if os.path.exists(full_path):
                img_human = cv2.imread(full_path)
                if img_human is not None: break
                    
        if img_human is None: img_human = img.copy()

        cropped_img = crop_to_aspect_ratio(img, 300, 400)
        resized_img = cv2.resize(cropped_img, (300, 400))
        
        cropped_img_alt = crop_to_aspect_ratio(img_alt, 300, 400)
        resized_img_alt = cv2.resize(cropped_img_alt, (300, 400))
        
        cropped_human = crop_to_aspect_ratio(img_human, 300, 400)
        resized_human = cv2.resize(cropped_human, (300, 400))
        
        targets.append((resized_img, resized_img_alt))
        angles = get_landmark_angles(resized_human)
        target_angles.append(angles if angles else [180.0, 180.0])

    captured_frames_raw = []
    pose_count = 1
    game_started = False
    user_quit = False

    def handle_prep_mouse(event, x, y, flags, param):
        global game_started
        prep_btn_x, prep_btn_y = (800 - 200) // 2, 530
        if prep_btn_x <= x <= prep_btn_x + 200 and prep_btn_y <= y <= prep_btn_y + 60:
            if event == cv2.EVENT_LBUTTONUP:
                game_started = True

    cv2.namedWindow("Imperfect Posers", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Imperfect Posers", handle_prep_mouse)

    while pose_count <= 4:
        ret, frame = cap.read()
        if not ret or frame is None: continue
        frame = cv2.flip(frame, 1)

        if not game_started:
            display_frame = bg_img.copy()
            gif_frame_idx = int(time.time() / 0.2) % 2
            current_target_img = targets[0][gif_frame_idx]
            
            cropped_target = crop_to_aspect_ratio(current_target_img, 225, 300)
            resized_target = cv2.resize(cropped_target, (225, 300))

            cropped_cam = crop_to_aspect_ratio(frame, 350, 262)
            resized_cam = cv2.resize(cropped_cam, (350, 262))

            display_frame[225:525, 90:315] = resized_target
            display_frame[244:506, 420:770] = resized_cam

            cv2.rectangle(display_frame, (90, 225), (315, 525), (246, 145, 255), 3)
            cv2.rectangle(display_frame, (420, 244), (770, 506), (246, 145, 255), 3)

            if game_logo_img is not None:
                overlay_png(display_frame, game_logo_img, (800 - 450) // 2, 1)
            else:
                cv2.putText(display_frame, "IMPERFECT POSERS", (300, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            
            prep_btn_x, prep_btn_y = (800 - 400) // 2, 530
            if start_btn_img is not None:
                overlay_png(display_frame, start_btn_img, prep_btn_x, prep_btn_y)
            else:
                cv2.rectangle(display_frame, (prep_btn_x, prep_btn_y), (prep_btn_x + 200, prep_btn_y + 55), (0, 255, 0), -1)
                cv2.putText(display_frame, "START", (prep_btn_x + 55, prep_btn_y + 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

            cv2.imshow("Imperfect Posers", display_frame)
            
            key = cv2.waitKey(1)
            if key == 27: 
                user_quit = True
                break
            elif key == 32: 
                game_started = True
            continue

        cv2.setMouseCallback("Imperfect Posers", lambda *args: None)

        countdown_start = time.time()
        captured_frame = None
        
        while time.time() - countdown_start < 3.0:
            ret, frame = cap.read()
            if not ret or frame is None: continue
            frame = cv2.flip(frame, 1)
            
            display_frame = bg_img.copy()
            gif_frame_idx = int(time.time() / 0.2) % 2
            current_target_img = targets[pose_count-1][gif_frame_idx]
            
            cropped_target = crop_to_aspect_ratio(current_target_img, 225, 300)
            resized_target = cv2.resize(cropped_target, (225, 300))
            
            cropped_cam = crop_to_aspect_ratio(frame, 350, 262)
            resized_cam = cv2.resize(cropped_cam, (350, 262))
            
            display_frame[225:525, 90:315] = resized_target
            display_frame[244:506, 420:770] = resized_cam
            
            cv2.rectangle(display_frame, (90, 225), (315, 525), (246, 145, 255), 3)
            cv2.rectangle(display_frame, (420, 244), (770, 506), (246, 145, 255), 3)

            if game_logo_img is not None:
                overlay_png(display_frame, game_logo_img, (800 - 450) // 2, 1)
            else:
                cv2.putText(display_frame, "IMPERFECT POSERS", (260, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            
            current_countdown = int(4.0 - (time.time() - countdown_start))
            cv2.putText(display_frame, f" {pose_count}/4", (340, 400), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (231, 150, 255), 2)
            cv2.putText(display_frame, str(current_countdown), (340, 370), cv2.FONT_HERSHEY_SIMPLEX, 3, (231, 150, 255), 5)
                
            cv2.imshow("Imperfect Posers", display_frame)
            
            key = cv2.waitKey(1)
            if key == 27:
                user_quit = True
                break
            captured_frame = frame

        if user_quit: break

        if captured_frame is not None:
            cropped_final = crop_to_aspect_ratio(captured_frame, 400, 300)
            resized_frame = cv2.resize(cropped_final, (400, 300))
            captured_frames_raw.append(resized_frame)
            pose_count += 1

    if user_quit: break

    # --- 1. 2x2 AI SCORE RESULTS SCREEN ---
    if len(captured_frames_raw) == 4:
        print("\n Photos captured! Calculating AI scores...")
        scores = []
        
        for idx, frame in enumerate(captured_frames_raw):
            current_angles = get_landmark_angles(frame)
            match_score = 0
            if current_angles and target_angles[idx]:
                c_left = current_angles[0] if current_angles[0] is not None else 180.0
                c_right = current_angles[1] if current_angles[1] is not None else 180.0
                t_left = target_angles[idx][0] if target_angles[idx][0] is not None else 180.0
                t_right = target_angles[idx][1] if target_angles[idx][1] is not None else 180.0
                
                diff1 = abs(c_left - t_left)
                diff2 = abs(c_right - t_right)
                leniency_factor = 0.5   
                match_score = max(0, int(100 - ((diff1 + diff2) / 2) * leniency_factor))                
            scores.append(match_score)

        score_state = {'next_clicked': False, 'btn_state': 1}

        def handle_2x2_mouse(event, x, y, flags, param):
            if 300 <= x <= 500 and 520 <= y <= 575:
                if event == cv2.EVENT_LBUTTONDOWN:
                    param['btn_state'] = 2
                elif event == cv2.EVENT_LBUTTONUP:
                    param['next_clicked'] = True
                else:
                    param['btn_state'] = 2
            else:
                param['btn_state'] = 1

        cv2.setMouseCallback("Imperfect Posers", handle_2x2_mouse, score_state)

        results_active = True
        while results_active:
            res_ui = bg_img.copy()
            
            # Header
            cv2.putText(res_ui, "YOUR AI POSE SCORES", (220, 45), cv2.FONT_HERSHEY_TRIPLEX, 0.9, (255, 255, 255), 2)
            
            # 2x2 Grid placement coordinates: [x, y, w, h]
            grid_positions = [
                (60, 65, 320, 200),   # Top-Left
                (420, 65, 320, 200),  # Top-Right
                (60, 290, 320, 200),  # Bottom-Left
                (420, 290, 320, 200)  # Bottom-Right
            ]
            
            for idx, (gx, gy, gw, gh) in enumerate(grid_positions):
                # Crop to grid box aspect ratio before resizing
                cropped_grid = crop_to_aspect_ratio(captured_frames_raw[idx], gw, gh)
                img_resized = cv2.resize(cropped_grid, (gw, gh))
                
                res_ui[gy:gy+gh, gx:gx+gw] = img_resized
                cv2.rectangle(res_ui, (gx, gy), (gx+gw, gy+gh), (246, 145, 255), 2)
                
                # Draw Pose Score Badge on each image
                score_txt = f"Pose {idx+1}: {scores[idx]}%"
                cv2.rectangle(res_ui, (gx, gy + gh - 35), (gx + 160, gy + gh), (20, 20, 20), -1)
                cv2.putText(res_ui, score_txt, (gx + 10, gy + gh - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

            # Draw "NEXT ->" button using next1.png / next2.png
            active_next_btn = nextbtn2 if score_state['btn_state'] == 2 and nextbtn2 is not None else nextbtn1
            if active_next_btn is not None:
                overlay_png(res_ui, active_next_btn, 300, 520)
            else:
                btn_col = (0, 220, 110) if score_state['btn_state'] == 2 else (0, 180, 90)
                cv2.rectangle(res_ui, (300, 520), (500, 575), btn_col, -1)
                cv2.rectangle(res_ui, (300, 520), (500, 575), (255, 255, 255), 2)
                cv2.putText(res_ui, "NEXT ->", (350, 558), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

            cv2.imshow("Imperfect Posers", res_ui)
            
            key = cv2.waitKey(30)
            if key == 27:
                user_quit = True
                break
            elif score_state['next_clicked']:
                results_active = False

        if user_quit: break

    # --- 2. PHOTOSTRIP CUSTOMIZATION STUDIO ---
    if len(captured_frames_raw) == 4:
        print(" Opening Photostrip Studio...")

        color_options = [
            ("White", (255, 255, 255)),
            ("Pink", (230, 200, 255)),
            ("Teal", (245, 230, 190)),
            ("Yellow", (200, 245, 255)),
            ("Purple", (245, 210, 235)),
            ("Black", (35, 35, 35))
        ]
        
        current_bg_color = color_options[0][1] 
        active_sticker = None
        placed_stickers = [] 
        again_button_state = 1  
        save_button_state = 1
        notification_msg = ""
        notification_time = 0

        disp_x, disp_y, disp_w, disp_h = 30, 25, 230, 565
        
        studio_active = {'active': True}

        def handle_studio_mouse(event, x, y, flags, param):
            global current_bg_color, active_sticker, placed_stickers, notification_msg, notification_time, game_running, again_button_state, save_button_state
            
            # Hover check for Save Photostrip Button (290, 360) -> (510, 420)
            if 290 <= x <= 510 and 360 <= y <= 420:
                if event == cv2.EVENT_LBUTTONDOWN:
                    save_button_state = 2
                elif event == cv2.EVENT_LBUTTONUP:
                    highres_strip = build_photostrip(captured_frames_raw, current_bg_color, placed_stickers)
                    out_p = os.path.join(TARGET_DIR, "self_photostrip.jpg")
                    cv2.imwrite(out_p, highres_strip)
                    notification_msg = f"Saved to self_photostrip.jpg!"
                    notification_time = time.time()
                    save_button_state = 2
                else:
                    save_button_state = 2
            else:
                save_button_state = 1

            # Hover check for Play Again Button (290, 440) -> (510, 500)
            if 290 <= x <= 510 and 440 <= y <= 500:
                if event == cv2.EVENT_LBUTTONDOWN:
                    again_button_state = 2
                elif event == cv2.EVENT_LBUTTONUP and again_button_state == 2:
                    param['active'] = False
                else:
                    again_button_state = 2
            else:
                again_button_state = 1

            if event == cv2.EVENT_LBUTTONDOWN:
                # 1. Click on Photostrip -> Place active sticker
                if disp_x <= x <= disp_x + disp_w and disp_y <= y <= disp_y + disp_h:
                    if active_sticker is not None:
                        hires_x = int((x - disp_x) * (360.0 / disp_w))
                        hires_y = int((y - disp_y) * (885.0 / disp_h))
                        placed_stickers.append((active_sticker, hires_x, hires_y))
                        notification_time = time.time()
                
                # 2. Color selection palette clicks
                for idx_c, (_, col_bgr) in enumerate(color_options):
                    bx = 290 + (idx_c * 80)
                    by = 130
                    if bx <= x <= bx + 65 and by <= y <= by + 45:
                        current_bg_color = col_bgr
                        notification_time = time.time()

                # 3. Sticker selection clicks
                stk_keys = ["pink", "purple", "teal", "yellow"]
                for idx_s, key in enumerate(stk_keys):
                    sx = 290 + (idx_s * 85)
                    sy = 250
                    if sx <= x <= sx + 70 and sy <= y <= sy + 60:
                        active_sticker = key
                        notification_msg = f"Selected {key.title()} Star"
                        notification_time = time.time()

                # Clear stickers button click (630, 250) -> (770, 310)
                if 630 <= x <= 770 and 250 <= y <= 310:
                    placed_stickers.clear()
                    notification_msg = "Stickers Cleared!"
                    notification_time = time.time()

        cv2.setMouseCallback("Imperfect Posers", handle_studio_mouse, studio_active)

        while studio_active['active']:
            highres_strip = build_photostrip(captured_frames_raw, current_bg_color, placed_stickers)
            studio_ui = bg_img.copy()
            
            preview_strip = cv2.resize(highres_strip, (disp_w, disp_h))
            cv2.rectangle(studio_ui, (disp_x - 3, disp_y - 3), (disp_x + disp_w + 3, disp_y + disp_h + 3), (255, 255, 255), 2)
            studio_ui[disp_y:disp_y+disp_h, disp_x:disp_x+disp_w] = preview_strip

            cv2.putText(studio_ui, "PHOTOSTRIP STUDIO", (290, 50), cv2.FONT_HERSHEY_TRIPLEX, 1.0, (255, 255, 255), 2)

            # COLOR PICKER SECTION
            cv2.putText(studio_ui, "Photostrip color:", (290, 105), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (120, 104, 118), 1)
            for idx_c, (c_name, col_bgr) in enumerate(color_options):
                bx = 290 + (idx_c * 80)
                by = 130
                cv2.rectangle(studio_ui, (bx, by), (bx + 65, by + 45), col_bgr, -1)
                border_col = (246, 255, 166) if current_bg_color == col_bgr else (180, 180, 180)
                cv2.rectangle(studio_ui, (bx, by), (bx + 65, by + 45), border_col, 2)

            # STICKER SECTION
            cv2.putText(studio_ui, "Stickers:", (290, 225), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (120, 104, 118), 1)
            stk_keys = ["pink", "purple", "teal", "yellow"]
            for idx_s, key in enumerate(stk_keys):
                sx = 290 + (idx_s * 85)
                sy = 250
                is_selected = (active_sticker == key)
                bg_box_col = (226, 211, 237) if not is_selected else (222, 186, 247)
                cv2.rectangle(studio_ui, (sx, sy), (sx + 70, sy + 60), bg_box_col, -1)
                cv2.rectangle(studio_ui, (sx, sy), (sx + 70, sy + 60), (0, 255, 255) if is_selected else (150, 150, 150), 2)
                
                stk_img = stickers[key]
                overlay_png(studio_ui, stk_img, sx + 12, sy + 7)

            # Clear stickers button (Uses clear.png)
            if clearbtn_img is not None:
                overlay_png(studio_ui, clearbtn_img, 630, 250)
            else:
                cv2.rectangle(studio_ui, (630, 250), (770, 310), (50, 50, 180), -1)
                cv2.rectangle(studio_ui, (630, 250), (770, 310), (200, 200, 200), 1)
                cv2.putText(studio_ui, "CLEAR", (665, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
                cv2.putText(studio_ui, "STICKERS", (652, 298), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            # ACTION BUTTONS
            # 1. Save Photostrip Button (Uses save1.png and save2.png)
            active_save_btn = savebtn2 if save_button_state == 2 and savebtn2 is not None else savebtn1
            if active_save_btn is not None:
                overlay_png(studio_ui, active_save_btn, 290, 360)
            else:
                btn_color = (0, 150, 80) if save_button_state == 2 else (0, 180, 100)
                cv2.rectangle(studio_ui, (320, 360), (480, 420), btn_color, -1)
                cv2.rectangle(studio_ui, (320, 360), (480, 420), (255, 255, 255), 2)
                cv2.putText(studio_ui, "SAVE PHOTOSTRIP", (310, 398), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

            # 2. Play Again Button (Uses again1.png and again2.png)
            active_again_btn = againbtn2 if again_button_state == 2 and againbtn2 is not None else againbtn1
            if active_again_btn is not None:
                overlay_png(studio_ui, active_again_btn, 290, 440)
            else:
                btn_color = (180, 80, 40) if again_button_state == 2 else (220, 100, 50)
                cv2.rectangle(studio_ui, (290, 440), (510, 500), btn_color, -1)
                cv2.rectangle(studio_ui, (290, 440), (510, 500), (255, 255, 255), 2)
                cv2.putText(studio_ui, "PLAY AGAIN", (340, 478), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Status Notification Banner
            if notification_msg and (time.time() - notification_time < 3.0):
                cv2.putText(studio_ui, notification_msg, (290, 545), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (116, 86, 117), 2)

            cv2.imshow("Imperfect Posers", studio_ui)
            
            if cv2.waitKey(30) == 27:
                game_running = False
                break

# Cleanup
cap.release()
cv2.destroyAllWindows()