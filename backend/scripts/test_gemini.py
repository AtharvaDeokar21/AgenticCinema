from app.shared.tools.gemini import GeminiClient


def main():
    client = GeminiClient()

    response = client.generate(
        "Give me one creative logline for a short film about Mumbai."
    )

    print(response.text)


if __name__ == "__main__":
    main()