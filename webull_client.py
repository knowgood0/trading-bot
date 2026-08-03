import os
import glob


def debug_option_files():
    try:
        target_files = []

        files = glob.glob(
            "/opt/render/project/src/.venv/lib/python3.14/site-packages/webull/**/*.py",
            recursive=True
        )

        for file in files:
            if (
                "place_option_request.py" in file
                or "order_operation_v2.py" in file
            ):
                with open(file, "r", errors="ignore") as f:
                    content = f.read()

                target_files.append({
                    "file": file,
                    "content": content[:8000]
                })

        return {
            "success": True,
            "files": target_files
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def test_webull_connection():
    return {
        "success": True,
        "message": "debug mode"
    }


def paper_buy_spy():
    return {
        "success": False,
        "message": "debug mode"
    }


def test_options():
    return debug_option_files()
