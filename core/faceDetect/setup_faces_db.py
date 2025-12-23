"""
setup_faces_db.py

Utility để setup và quản lý faces database cho face recognition.

Cách sử dụng:
1. Tạo thư mục cho nhân vật: python setup_faces_db.py --add-character "Nguyen Van A"
2. Thêm ảnh từ video: python setup_faces_db.py --extract-faces video.mp4 --character "Nguyen Van A"
3. Liệt kê nhân vật: python setup_faces_db.py --list
4. Kiểm tra database: python setup_faces_db.py --check
"""

import os
import sys
import cv2
import argparse
from pathlib import Path
from typing import List, Optional

# Giảm log
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

try:
    from deepface import DeepFace
    HAS_DEEPFACE = True
except ImportError:
    HAS_DEEPFACE = False


def get_default_db_path() -> Path:
    """Lấy đường dẫn mặc định cho faces_db"""
    return Path(__file__).parent / "faces_db"


def list_characters(db_path: Path) -> List[str]:
    """Liệt kê các nhân vật trong database"""
    if not db_path.exists():
        return []

    characters = []
    for item in db_path.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            images = list(item.glob("*.jpg")) + list(item.glob("*.png")) + list(item.glob("*.jpeg"))
            characters.append({
                'name': item.name,
                'image_count': len(images),
                'path': str(item)
            })

    return characters


def add_character(db_path: Path, character_name: str) -> bool:
    """Tạo thư mục cho nhân vật mới"""
    char_path = db_path / character_name
    char_path.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Created character folder: {char_path}")
    print(f"     Add face images (jpg/png) to this folder")
    return True


def extract_faces_from_video(
    video_path: str,
    character_name: str,
    db_path: Path,
    max_faces: int = 10,
    sample_interval: float = 2.0
) -> int:
    """
    Trích xuất faces từ video và lưu vào thư mục nhân vật.
    Người dùng cần verify thủ công các ảnh.

    Args:
        video_path: Đường dẫn video
        character_name: Tên nhân vật
        db_path: Đường dẫn database
        max_faces: Số lượng ảnh tối đa cần trích xuất
        sample_interval: Khoảng cách giữa các frame (giây)

    Returns:
        Số lượng faces đã trích xuất
    """
    if not HAS_DEEPFACE:
        print("[ERROR] DeepFace not installed. Cannot extract faces.")
        return 0

    char_path = db_path / character_name
    char_path.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {video_path}")
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    frame_step = int(fps * sample_interval)
    if frame_step < 1:
        frame_step = 1

    print(f"[INFO] Extracting faces from: {video_path}")
    print(f"       FPS: {fps:.1f}, Total frames: {total_frames}")
    print(f"       Sample every {sample_interval}s ({frame_step} frames)")

    extracted = 0
    frame_idx = 0

    while extracted < max_faces:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()

        if not ret:
            break

        try:
            # Detect faces in frame
            faces = DeepFace.extract_faces(
                img_path=frame,
                detector_backend='opencv',
                enforce_detection=False
            )

            for i, face_data in enumerate(faces):
                if extracted >= max_faces:
                    break

                face_img = face_data.get('face')
                confidence = face_data.get('confidence', 0)

                if face_img is not None and confidence > 0.8:
                    # Convert to BGR for saving
                    if face_img.max() <= 1.0:
                        face_img = (face_img * 255).astype('uint8')

                    # Resize to standard size
                    face_img = cv2.resize(face_img, (224, 224))

                    # Convert RGB to BGR for cv2.imwrite
                    face_img_bgr = cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR)

                    # Save
                    output_path = char_path / f"face_{frame_idx}_{i}.jpg"
                    cv2.imwrite(str(output_path), face_img_bgr)

                    extracted += 1
                    print(f"  Extracted face {extracted}/{max_faces}: {output_path.name}")

        except Exception as e:
            pass  # Skip frames with errors

        frame_idx += frame_step

        # Progress
        progress = (frame_idx / total_frames) * 100
        if frame_idx % (frame_step * 10) == 0:
            print(f"  Progress: {progress:.0f}%")

    cap.release()

    print(f"\n[OK] Extracted {extracted} faces to: {char_path}")
    print(f"     IMPORTANT: Please review and delete incorrect faces!")
    return extracted


def check_database(db_path: Path) -> bool:
    """Kiểm tra và validate database"""
    print(f"\n=== Faces Database Check ===")
    print(f"Path: {db_path}")

    if not db_path.exists():
        print(f"[WARNING] Database folder does not exist!")
        print(f"  Creating: {db_path}")
        db_path.mkdir(parents=True, exist_ok=True)
        return False

    characters = list_characters(db_path)

    if not characters:
        print(f"[WARNING] No characters in database!")
        print(f"\nTo add a character:")
        print(f"  python setup_faces_db.py --add-character \"Character Name\"")
        return False

    print(f"\nCharacters ({len(characters)}):")
    for char in characters:
        status = "[OK]" if char['image_count'] >= 3 else "[WARN: need more images]"
        print(f"  - {char['name']}: {char['image_count']} images {status}")

    # Validate with DeepFace
    if HAS_DEEPFACE:
        print(f"\n[Testing] DeepFace recognition...")
        try:
            # Test với 1 character
            test_char = characters[0]
            test_path = Path(test_char['path'])
            images = list(test_path.glob("*.jpg")) + list(test_path.glob("*.png"))

            if images:
                # Read first image
                img = cv2.imread(str(images[0]))
                result = DeepFace.represent(
                    img_path=img,
                    model_name='VGG-Face',
                    enforce_detection=False
                )
                print(f"  [OK] DeepFace is working correctly")
        except Exception as e:
            print(f"  [ERROR] DeepFace test failed: {e}")
            return False
    else:
        print(f"\n[WARNING] DeepFace not installed!")
        print(f"  Install with: pip install deepface")

    print(f"\n[OK] Database ready for face recognition")
    return True


def interactive_add_from_image(db_path: Path, image_path: str, character_name: str):
    """Thêm face từ ảnh có sẵn"""
    if not HAS_DEEPFACE:
        print("[ERROR] DeepFace not installed")
        return False

    char_path = db_path / character_name
    char_path.mkdir(parents=True, exist_ok=True)

    try:
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            print(f"[ERROR] Cannot read image: {image_path}")
            return False

        # Extract faces
        faces = DeepFace.extract_faces(
            img_path=img,
            detector_backend='opencv',
            enforce_detection=False
        )

        if not faces:
            print(f"[WARNING] No faces detected in image")
            # Copy whole image
            import shutil
            output_path = char_path / Path(image_path).name
            shutil.copy(image_path, output_path)
            print(f"[OK] Copied original image to: {output_path}")
            return True

        # Save each face
        for i, face_data in enumerate(faces):
            face_img = face_data.get('face')

            if face_img is not None:
                if face_img.max() <= 1.0:
                    face_img = (face_img * 255).astype('uint8')

                face_img = cv2.resize(face_img, (224, 224))
                face_img_bgr = cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR)

                output_name = f"{Path(image_path).stem}_face_{i}.jpg"
                output_path = char_path / output_name
                cv2.imwrite(str(output_path), face_img_bgr)
                print(f"[OK] Saved face to: {output_path}")

        return True

    except Exception as e:
        print(f"[ERROR] Failed to extract face: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Setup and manage faces database for face recognition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all characters
  python setup_faces_db.py --list

  # Add new character
  python setup_faces_db.py --add-character "John Doe"

  # Extract faces from video
  python setup_faces_db.py --extract-faces video.mp4 --character "John Doe"

  # Add face from image
  python setup_faces_db.py --add-image photo.jpg --character "John Doe"

  # Check database health
  python setup_faces_db.py --check
        """
    )

    parser.add_argument("--db-path", help="Path to faces_db folder (default: core/faceDetect/faces_db)")
    parser.add_argument("--list", action="store_true", help="List all characters")
    parser.add_argument("--check", action="store_true", help="Check database health")
    parser.add_argument("--add-character", metavar="NAME", help="Add new character folder")
    parser.add_argument("--extract-faces", metavar="VIDEO", help="Extract faces from video")
    parser.add_argument("--add-image", metavar="IMAGE", help="Add face from image file")
    parser.add_argument("--character", metavar="NAME", help="Character name (for extract/add)")
    parser.add_argument("--max-faces", type=int, default=10, help="Max faces to extract (default: 10)")

    args = parser.parse_args()

    # Get database path
    db_path = Path(args.db_path) if args.db_path else get_default_db_path()

    # Execute command
    if args.list:
        characters = list_characters(db_path)
        if characters:
            print(f"Characters in {db_path}:")
            for char in characters:
                print(f"  - {char['name']}: {char['image_count']} images")
        else:
            print(f"No characters found in {db_path}")

    elif args.check:
        check_database(db_path)

    elif args.add_character:
        add_character(db_path, args.add_character)

    elif args.extract_faces:
        if not args.character:
            print("[ERROR] Please specify --character NAME")
            sys.exit(1)
        extract_faces_from_video(
            args.extract_faces,
            args.character,
            db_path,
            max_faces=args.max_faces
        )

    elif args.add_image:
        if not args.character:
            print("[ERROR] Please specify --character NAME")
            sys.exit(1)
        interactive_add_from_image(db_path, args.add_image, args.character)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
