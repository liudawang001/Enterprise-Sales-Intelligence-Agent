"""Create the synthetic Demo PDF used by the local RAG upload example."""
from pathlib import Path

import fitz


def main() -> None:
    output = Path("data/demo_documents/demo_group_vnet.pdf")
    output.parent.mkdir(parents=True, exist_ok=True)
    font = "/System/Library/Fonts/Hiragino Sans GB.ttc"
    document = fitz.open()
    pages = [
        "集团V网 Demo 业务说明",
        "集团V网主要面向具有企业内部通信需求的集团客户。多办公地点的制造业、物流和连锁企业优先。",
        "集团V网支持企业内部短号通信和跨省V网能力，适合总部与分支机构之间的通信场景。",
        "集团V网办理条件包括企业主体资料、联系人信息和业务申请材料，具体以授权业务文件为准。",
    ]
    for text in pages:
        page = document.new_page()
        page.insert_font(fontname="zh", fontfile=font)
        page.insert_text((72, 72), text, fontname="zh", fontsize=12)
    document.save(output)
    print(output)


if __name__ == "__main__":
    main()
