import asyncio

from app.shared.tools.parallel.search import ParallelSearch


async def main():
    search = ParallelSearch()

    response = await search.search(
        search_queries=[
            "Mumbai night photography locations",
            "Mumbai night culture",
        ],
        objective=(
            "Find factual information useful for a cinematic script "
            "about a photographer discovering Mumbai at night."
        ),
    )

    print("\nRESPONSE TYPE:")
    print(type(response))

    print("\nRESPONSE:")
    print(response)

    await search.client.close()


if __name__ == "__main__":
    asyncio.run(main())