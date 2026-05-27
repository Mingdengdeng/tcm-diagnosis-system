from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeSource:
    key: str
    name: str
    url: str
    license: str
    commercial_use: bool
    recommended_use: str
    notes: str


COMMERCIAL_SAFE_SOURCES = {
    "original_curated_tcm": KnowledgeSource(
        key="original_curated_tcm",
        name="Original curated TCM safety and question-flow content",
        url="local://tcm_demo/knowledge.py",
        license="Project-owned original content",
        commercial_use=True,
        recommended_use="Question bank, symptom keywords, safe pattern evidence, and app-specific examples.",
        notes="Use this as the main product knowledge layer; keep citations as rationale, not copied text.",
    ),
    "cblue": KnowledgeSource(
        key="cblue",
        name="CBLUE Chinese Biomedical Language Understanding Evaluation Benchmark",
        url="https://github.com/cbluebenchmark/cblue",
        license="Apache-2.0",
        commercial_use=True,
        recommended_use="Chinese medical NLP evaluation patterns such as NER, relation extraction, query intent, and similarity.",
        notes="Best used for evaluation and NLP task design, not as direct TCM diagnostic truth.",
    ),
    "toc_medical_dialogue": KnowledgeSource(
        key="toc_medical_dialogue",
        name="Target-oriented Conversation medical dialogue datasets",
        url="https://targetconversation-sysu.github.io/",
        license="CC BY 4.0",
        commercial_use=True,
        recommended_use="Multi-turn medical dialogue flow design and evaluation examples with attribution.",
        notes="Attribution is required. Avoid copying patient-like text into product prompts unless privacy and dataset terms are reviewed.",
    ),
    "icd11_tm": KnowledgeSource(
        key="icd11_tm",
        name="WHO ICD-11 Traditional Medicine Chapter / ICD API",
        url="https://icd.who.int/icdapi/docs2/license/",
        license="CC BY-ND 3.0 IGO",
        commercial_use=True,
        recommended_use="Terminology alignment and code lookup without modifying WHO classification text.",
        notes="NoDerivatives means do not rewrite or redistribute modified WHO classification content as if it were the source.",
    ),
    "medlineplus_xml": KnowledgeSource(
        key="medlineplus_xml",
        name="MedlinePlus XML files",
        url="https://medlineplus.gov/xml.html",
        license="NLM downloadable XML use with attribution; verify page-level third-party content before redistribution",
        commercial_use=True,
        recommended_use="General health red flags, patient-friendly safety language, and doctor-consultation guidance.",
        notes="Use attribution. Avoid images and vendor-licensed page content unless separately cleared.",
    ),
    "public_domain_classics": KnowledgeSource(
        key="public_domain_classics",
        name="Public-domain TCM classics",
        url="https://commons.wikimedia.org/wiki/File:The_Su_Wen_of_the_Huangdi_Neijing.djvu",
        license="Public domain where confirmed",
        commercial_use=True,
        recommended_use="High-level historical terminology rationale only.",
        notes="Classical text is not enough for modern triage. Verify each scan/transcription license before reuse.",
    ),
}


REFERENCE_ONLY_SOURCES = {
    "who_ist_tcm": KnowledgeSource(
        key="who_ist_tcm",
        name="WHO International Standard Terminologies on Traditional Medicine",
        url="https://iris.who.int/handle/10665/206952",
        license="WHO publication; check reuse terms before embedding content",
        commercial_use=False,
        recommended_use="Reference terminology during manual curation.",
        notes="Do not bulk-copy into a commercial app without a separate rights review.",
    ),
    "tcm_mkg": KnowledgeSource(
        key="tcm_mkg",
        name="Traditional Chinese Medicine Multidimensional Knowledge Graph",
        url="https://zenodo.org/records/19804367",
        license="CC BY-NC 4.0",
        commercial_use=False,
        recommended_use="Non-commercial research reference only.",
        notes="NonCommercial license is not compatible with a product you may sell.",
    ),
}


def get_source_policy(source: str) -> KnowledgeSource | None:
    return COMMERCIAL_SAFE_SOURCES.get(source) or REFERENCE_ONLY_SOURCES.get(source)


def is_commercial_safe_source(source: str) -> bool:
    policy = get_source_policy(source)
    return bool(policy and policy.commercial_use)


def commercial_safe_source_summary() -> list[dict[str, str | bool]]:
    return [
        {
            "key": source.key,
            "name": source.name,
            "license": source.license,
            "commercial_use": source.commercial_use,
            "recommended_use": source.recommended_use,
            "url": source.url,
        }
        for source in COMMERCIAL_SAFE_SOURCES.values()
    ]
