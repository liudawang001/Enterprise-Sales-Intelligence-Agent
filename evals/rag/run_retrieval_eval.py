import json
from pathlib import Path
from uuid import uuid4

from app.knowledge.enums import DocumentAuthority, DocumentStatus
from app.knowledge.ingestion.tokenizer import JiebaLexicalTokenizer
from app.knowledge.models import KnowledgeChunk, KnowledgeDocument, KnowledgeQuery
from app.knowledge.repository import InMemoryKnowledgeRepository
from app.knowledge.rerank.fake import FakeReranker
from app.knowledge.retrieval.dense import DenseRetriever
from app.knowledge.retrieval.filters import MetadataFilterBuilder
from app.knowledge.retrieval.hybrid import HybridRetriever
from app.knowledge.retrieval.rrf import ReciprocalRankFusion
from app.knowledge.retrieval.sparse import PostgresSparseRetriever
from app.providers.embedding.fake import DeterministicFakeEmbedding
from evals.rag.metrics import mrr, recall_at_k


def build_demo_repository() -> tuple[InMemoryKnowledgeRepository, dict[str, list[str]]]:
    repository = InMemoryKnowledgeRepository()
    document = KnowledgeDocument(id=uuid4(), title="集团V网 Demo 业务说明", original_filename="demo_group_vnet.pdf", file_hash="f" * 64, business="集团V网", region="NATIONAL", authority=DocumentAuthority.DEMO, status=DocumentStatus.READY, file_path="data/demo_documents/demo_group_vnet.pdf")
    repository.create_document(document)
    pages = {
        2: "集团V网主要面向具有企业内部通信需求的集团客户，多办公地点的制造业、物流和连锁企业优先。",
        3: "集团V网支持企业内部短号通信和跨省V网能力，适合总部与分支机构之间的通信场景。",
        4: "集团V网办理条件包括企业主体资料、联系人信息和业务申请材料，具体以授权业务文件为准。",
    }
    embedding = DeterministicFakeEmbedding()
    gold_by_page: dict[str, list[str]] = {}
    for page, content in pages.items():
        chunk = KnowledgeChunk(id=uuid4(), document_id=document.id, chunk_index=page, content=content, lexical_content=JiebaLexicalTokenizer().tokenize(content), embedding=embedding.embed_query(content), page_start=page, page_end=page, content_hash=str(page) * 64, metadata={"document_title": document.title, "authority": "DEMO", "region": "NATIONAL"})
        repository.replace_chunks(document.id, [*repository.list_chunks(document.id), chunk])
        gold_by_page[str(page)] = [str(chunk.id)]
    return repository, gold_by_page


def main() -> None:
    dataset = [json.loads(line) for line in (Path(__file__).parent / "dataset.jsonl").read_text().splitlines()]
    repository, gold_by_page = build_demo_repository()
    embedding = DeterministicFakeEmbedding()
    dense = DenseRetriever(repository, embedding)
    sparse = PostgresSparseRetriever(repository, JiebaLexicalTokenizer())
    fusion = ReciprocalRankFusion()
    hybrid = HybridRetriever(dense, sparse, fusion, FakeReranker())
    rankings = {name: [] for name in ("Dense", "Sparse", "Hybrid", "Hybrid + Reranker")}
    expected: list[set[str]] = []
    answerable = [item for item in dataset if item["answerable"]]
    for item in answerable:
        query = KnowledgeQuery(raw_query=item["question"], rewritten_query=item["question"], business=item["business"], region=item["region"])
        filter_ = MetadataFilterBuilder().build(query)
        dense_hits = dense.search(query.rewritten_query, knowledge_filter=filter_, top_k=5)
        sparse_hits = sparse.search(query.rewritten_query, knowledge_filter=filter_, top_k=5)
        fused = fusion.fuse(dense_hits, sparse_hits, top_k=5)
        reranked, _ = __import__("asyncio").run(hybrid.search(query.rewritten_query, knowledge_filter=filter_, fusion_top_k=5, rerank_top_k=5))
        rankings["Dense"].append([hit.chunk_id for hit in dense_hits])
        rankings["Sparse"].append([hit.chunk_id for hit in sparse_hits])
        rankings["Hybrid"].append([hit.chunk_id for hit in fused])
        rankings["Hybrid + Reranker"].append([hit.chunk_id for hit in reranked])
        pages = {2: "2", 3: "3", 4: "4"}
        expected.append(set(gold_by_page[pages[item["expected_pages"][0]]]))
    print("Method                  Recall@5     MRR")
    for name, ranking in rankings.items():
        print(f"{name:<23} {recall_at_k(ranking, expected):.3f}        {mrr(ranking, expected):.3f}")
    print(f"Dataset size: {len(dataset)} (answerable={len(answerable)}, negative={len(dataset)-len(answerable)})")


if __name__ == "__main__":
    main()
