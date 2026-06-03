from wechat_writer import create_app, ensure_runtime_dirs
from wechat_writer.config import PORT


app = create_app()


if __name__ == "__main__":
    ensure_runtime_dirs()
    app.run(host="0.0.0.0", port=PORT, debug=False)
