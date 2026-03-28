from app import create_app


def main() -> int:
    app = create_app()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
