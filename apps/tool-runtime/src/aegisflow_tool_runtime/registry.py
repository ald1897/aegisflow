from aegisflow_tool_runtime.schemas import ToolDefinition


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "borrower_profile_lookup": ToolDefinition(
        tool_id="borrower_profile_lookup",
        display_name="Borrower Profile Lookup",
        description="Returns deterministic masked borrower profile context for mortgage exception review.",
        allowed_agents=["intake_agent"],
        input_schema="BorrowerProfileLookupInput",
        output_schema="BorrowerProfileLookupOutput",
        data_classification="Confidential",
        replay_safe=True,
    ),
    "document_fetch": ToolDefinition(
        tool_id="document_fetch",
        display_name="Document Fetch",
        description="Returns deterministic mortgage document metadata without raw document content.",
        allowed_agents=["document_analysis_agent"],
        input_schema="DocumentFetchInput",
        output_schema="DocumentFetchOutput",
        data_classification="Confidential",
        replay_safe=True,
    ),
    "fraud_signal_lookup": ToolDefinition(
        tool_id="fraud_signal_lookup",
        display_name="Fraud Signal Lookup",
        description="Returns deterministic high-level fraud signal metadata for human risk review preparation.",
        allowed_agents=["document_analysis_agent"],
        input_schema="FraudSignalLookupInput",
        output_schema="FraudSignalLookupOutput",
        data_classification="Confidential",
        replay_safe=True,
    ),
}
