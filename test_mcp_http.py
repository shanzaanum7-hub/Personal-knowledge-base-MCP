import asyncio
from fastmcp import Client


async def main():
    async with Client("http://127.0.0.1:8000/mcp/") as client:
        result = await client.call_tool(
            "search_notes",
            {
                "query": "CPU Scheduling",
                "user_id": "user-123",
                "top_k": 5,
            },
        )

        print("MCP tool call successful!")
        print("Result:")
        
        for content in result:
            print(content)


if __name__ == "__main__":
    asyncio.run(main())