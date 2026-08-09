import os
from mcp_server import send_email_report, evaluate_spectra_qa

def test():
    print("=== Testing MCP Tool: send_email_report ===")
    # Testing the email endpoint which should already exist on port 5000
    email_result = send_email_report(
        to_email="test@example.com",
        subject="MCP Automated Evaluation Test",
        report_body="This is a test of the MCP email reporting tool.\nEverything is working."
    )
    print("Result:")
    print(email_result)

    print("\n=== Testing MCP Tool: evaluate_spectra_qa ===")
    print("Note: If the backend hasn't been restarted, this might return a 405 Error.")
    eval_result = evaluate_spectra_qa(
        document_content="This is a test document.",
        document_type="Requirement",
        target_email="test@example.com"
    )
    print("Result:")
    print(eval_result)

if __name__ == "__main__":
    test()
