"""
Utility functions to filter question data for different agents.

Agent 2 (Solution Generator) only needs semantic data (question_data).
Agent 3 (Action Generator) only needs technical data (interaction_data).
"""
from typing import Dict, List, Any, Optional


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
        return {
            "id": question.get("id"),
            "type": question.get("type"),
            "question_data": question.get("question_data"),
        }

    # Fallback for old schema (backward compatibility during transition)
    return {
        "question_id": question.get("question_id"),
        "question_type": question.get("question_type"),
        "title": question.get("title"),
        "description": question.get("description"),
        "context": question.get("context"),
        "hints": question.get("hints"),
        "metadata": question.get("metadata"),
        # Omit inputs/selectors - Agent 2 doesn't need technical details
    }


def extract_interaction_data_for_agent_3(
    question: Dict[str, Any],
    solution: str
) -> Dict[str, Any]:
    """
    Extract only the technical interaction_data portion for Agent 3 (Action Generator).

    Agent 3 needs to know HOW to interact with the form, not WHAT the question means.

    Args:
        question: Complete question dict from Agent 1 (with new schema)
        solution: The generated solution from Agent 2

    Returns:
        Filtered dict with only interaction_data and minimal metadata
    """
    # Handle new schema (with question_data/interaction_data split)
    if "interaction_data" in question:
        return {
            "id": question.get("id"),
            "type": question.get("type"),
            "interaction_data": question.get("interaction_data"),
            "solution": solution,
        }

    # Fallback for old schema (backward compatibility during transition)
    return {
        "question_id": question.get("question_id"),
        "question_type": question.get("question_type"),
        "inputs": question.get("inputs", []),
        "metadata": question.get("metadata"),
        "solution": solution,
        # Omit title/description/context - Agent 3 doesn't need semantic context
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
