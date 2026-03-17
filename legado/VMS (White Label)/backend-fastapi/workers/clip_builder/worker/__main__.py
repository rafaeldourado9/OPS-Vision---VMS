import asyncio
from .service import ClipBuilderWorker


async def main():
    worker = ClipBuilderWorker()
    await worker.consume_queue()


if __name__ == '__main__':
    asyncio.run(main())
