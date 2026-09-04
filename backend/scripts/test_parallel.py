import asyncio

from app.shared.tools.parallel import ParallelSearch


async def main():
    search = ParallelSearch()

    response = await search.search(
        search_queries=[
            "Indian short film storytelling trends",
            "Indian cinema audience trends 2026",
            "Mumbai filmmaking cultural trends",
        ],
        objective=(
            "Research current Indian filmmaking and storytelling "
            "trends that could inspire a short-form film concept."
        ),
        mode="basic",
    )

    print("\n=== PARALLEL SEARCH RESULTS ===\n")

    print(response)

    await search.client.close()


if __name__ == "__main__":
    asyncio.run(main())