from aegisflow_agent_runtime.schemas import AgentRegistryEntry


AGENT_REGISTRY: dict[str, AgentRegistryEntry] = {
    "intake_agent": AgentRegistryEntry(
        agent_id="intake_agent",
        display_name="Intake Agent",
        description="Classifies mortgage exception review intake context and confirms readiness for document analysis.",
        prompt_id="intake-agent",
        prompt_version="1",
        supported_workflow_states=["INTAKE_IN_PROGRESS"],
        allowed_tools=["borrower_profile_lookup"],
        confidence_threshold=0.75,
    ),
    "document_analysis_agent": AgentRegistryEntry(
        agent_id="document_analysis_agent",
        display_name="Document Analysis Agent",
        description="Reviews provided mortgage document metadata and produces structured review signals for risk review.",
        prompt_id="document-analysis-agent",
        prompt_version="1",
        supported_workflow_states=["DOCUMENT_ANALYSIS_PENDING"],
        allowed_tools=["document_fetch"],
        confidence_threshold=0.80,
    ),
}
