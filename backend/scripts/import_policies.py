#!/usr/bin/env python3
"""政策导入脚本 — PDF/DOCX → Pipeline → pgvector

用法:
    python import_policies.py --seed              # 导入 8 条种子政策 (Mock 数据)
    python import_policies.py --file policy.pdf   # 导入单个 PDF
    python import_policies.py --dir ./policies/   # 批量导入目录
    python import_policies.py --status            # 查看导入状态
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# 确保项目路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def import_seed_policies():
    """导入 8 条 v1.1 种子政策到 policy_chunks 表"""
    from app.tools.adapters.policy_mock import PolicyMockData
    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore
    from app.services.chunker import ChunkData

    policies = PolicyMockData._POLICIES
    emb_svc = EmbeddingService(provider="mock", dimensions=1536)
    vs = VectorStore()

    total_chunks = 0
    for policy in policies:
        pid = policy["policy_id"]
        chunks_data = [
            ChunkData(
                chunk_id=f"{pid}-c000",
                policy_id=pid,
                chunk_index=0,
                content=policy["summary"],
                content_hash="",
                token_count=len(policy["summary"]) // 2,
                metadata={
                    "title": policy["title"],
                    "level": policy["level"],
                    "department": policy["department"],
                    "region": policy.get("region", ""),
                    "publish_date": policy.get("publish_date", ""),
                    "expire_date": policy.get("expire_date", ""),
                    "keywords": policy.get("keywords", []),
                },
            )
        ]
        embeddings = emb_svc.embed_sync([c.content for c in chunks_data])
        count = await vs.upsert_chunks(chunks_data, embeddings)
        total_chunks += count
        print(f"  ✅ {pid}: {policy['title'][:40]}... ({count} chunks)")

    print(f"\n✅ 导入完成: {total_chunks} chunks from {len(policies)} policies")
    return total_chunks


async def import_file(filepath: str):
    """导入单个政策文档"""
    from app.services.document_parser import DocumentParser
    from app.services.metadata_extractor import MetadataExtractor
    from app.services.chunker import TextChunker
    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore

    # 1. 解析
    parser = DocumentParser()
    doc = await parser.parse(filepath)
    if not doc.is_valid:
        print(f"❌ 解析失败: {doc.error}")
        return 0

    print(f"📄 {doc.filename}: {doc.page_count} pages, {len(doc.raw_text)} chars")

    # 2. 元数据
    extractor = MetadataExtractor()
    meta = extractor.extract(doc.raw_text, doc.filename)
    print(f"  标题: {meta.title[:50]}")
    print(f"  级别: {meta.level}, 部门: {meta.department}")

    # 3. 分块
    chunker = TextChunker(chunk_size=512, overlap=50)
    pid = f"POL-IMPORT-{Path(filepath).stem[:20]}"
    chunks = chunker.chunk(doc.raw_text, meta, policy_id=pid)
    print(f"  分块: {len(chunks)} chunks")

    # 4. Embedding
    emb_svc = EmbeddingService(provider="mock", dimensions=1536)
    embeddings = emb_svc.embed_sync([c.content for c in chunks])

    # 5. 写入
    vs = VectorStore()
    count = await vs.upsert_chunks(chunks, embeddings)
    print(f"  ✅ 写入 {count}/{len(chunks)} chunks")

    # 6. 索引
    await vs.ensure_index()
    return count


async def import_directory(dirpath: str):
    """批量导入目录中的文档"""
    path = Path(dirpath)
    files = list(path.glob("*.pdf")) + list(path.glob("*.docx")) + list(path.glob("*.txt"))
    total = 0
    for f in files:
        total += await import_file(str(f))
    print(f"\n✅ 批量导入完成: {total} total chunks")
    return total


async def show_status():
    """查看 RAG 状态"""
    from app.services.vector_store import VectorStore
    vs = VectorStore()
    count = await vs.count_chunks()
    from app.config import get_settings
    s = get_settings()
    print(f"RAG Mode:   {s.policy_rag_mode}")
    print(f"Embedding:  {s.policy_embedding_model} ({s.policy_embedding_dimensions}d)")
    print(f"Chunks:     {count}")
    print(f"Provider:   {s.policy_embedding_provider}")


async def main():
    parser = argparse.ArgumentParser(description="Policy RAG import tool")
    parser.add_argument("--seed", action="store_true", help="导入 8 条种子政策")
    parser.add_argument("--file", type=str, help="导入单个文件")
    parser.add_argument("--dir", type=str, help="批量导入目录")
    parser.add_argument("--status", action="store_true", help="查看状态")
    args = parser.parse_args()

    if args.seed:
        await import_seed_policies()
    elif args.file:
        await import_file(args.file)
    elif args.dir:
        await import_directory(args.dir)
    elif args.status:
        await show_status()
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
