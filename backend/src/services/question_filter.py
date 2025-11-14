"""
Utility functions to filter question data for different agents.

Agent 2 (Solution Generator) only needs semantic data (question_data).
Agent 3 (Action Generator) only needs technical data (interaction_data).
"""
from typing import Dict, List, Any, Optional


def _strip_nulls_and_empty_lists(value: Any) -> Any:
    """Return a copy without None values or empty lists."""
    if isinstance(value, dict):
        cleaned = {
            key: _strip_nulls_and_empty_lists(val)
            for key, val in value.items()
        }
        return {
            key: val
            for key, val in cleaned.items()
            if val is not None and not (isinstance(val, list) and len(val) == 0)
        }
    if isinstance(value, list):
        cleaned_list = [
            _strip_nulls_and_empty_lists(item)
            for item in value
        ]
        return [
            item
            for item in cleaned_list
            if item is not None and not (isinstance(item, list) and len(item) == 0)
        ]
    return value


def extract_question_data_for_agent_2(question: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract only the semantic question_data portion for Agent 2 (Solution Generator).

    Agent 2 needs to understand WHAT answer to generate, not HOW to interact.

    Args:
        question: Complete question dict from Agent 1 (with new schema)

    Returns:
        Filtered dict with only question_data and minimal metadata
    """
    # Handle new schema (with question_data/interaction_data split)
    if "question_data" in question:
        cleaned_question_data = _strip_nulls_and_empty_lists(
            question.get("question_data")
        )
        return {
            "id": question.get("id"),
            "type": question.get("type"),
            "question_data": cleaned_question_data,
        }
    
    # Fallback for old schema (backward compatibility during transition)
    return question


def extract_interaction_data_for_agent_3(
    question: Dict[str, Any],
    solution: str
) -> Dict[str, Any]:
    """
    Extract the technical interaction_data and question_data for Agent 3 (Action Generator).

    Agent 3 needs to know HOW to interact with the form (interaction_data)
    AND the original question text (question_data) to populate the question field in actions.

    Args:
        question: Complete question dict from Agent 1 (with new schema)
        solution: The generated solution from Agent 2

    Returns:
        Filtered dict with interaction_data, question_data, and minimal metadata
    """
    # Handle new schema (with question_data/interaction_data split)
    if "interaction_data" in question:
        return {
            "id": question.get("id"),
            "type": question.get("type"),
            "interaction_data": question.get("interaction_data"),
            "question_data": question.get("question_data"),
            "solution": solution,
        }

    # Fallback for old schema (backward compatibility during transition)
    return {
        "question_id": question.get("question_id"),
        "question_type": question.get("question_type"),
        "inputs": question.get("inputs", []),
        "metadata": question.get("metadata"),
        "solution": solution,
    }


def filter_questions_for_agent_2(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter a list of questions for Agent 2 (Solution Generator).

    Args:
        questions: List of complete questions from Agent 1

    Returns:
        List of filtered questions with only question_data
    """
    return [extract_question_data_for_agent_2(q) for q in questions]


def filter_question_solution_pairs_for_agent_3(
    question_solution_pairs: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Filter question-solution pairs for Agent 3 (Action Generator).

    Args:
        question_solution_pairs: List of dicts with 'question' and 'solution' keys

    Returns:
        List of filtered pairs with only interaction_data
    """
    filtered = []
    for pair in question_solution_pairs:
        question = pair.get("question", {})
        solution = pair.get("solution", "")
        filtered.append(extract_interaction_data_for_agent_3(question, solution))
    return filtered
