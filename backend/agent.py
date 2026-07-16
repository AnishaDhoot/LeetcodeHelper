import os
import json
import re
from dotenv import load_dotenv
import ollama
from groq import Groq

# Load environment variables
load_dotenv()

# Determine client based on configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

def query_ollama(prompt: str, system_prompt: str) -> str:
    """Queries the local Ollama instance."""
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            options={"temperature": 0.2}
        )
        return response["message"]["content"]
    except Exception as e:
        print(f"Error querying Ollama: {e}")
        raise e

def query_groq(prompt: str, system_prompt: str) -> str:
    """Queries Groq API as a cloud fallback."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY environment variable is not set")
    try:
        client = Groq(api_key=GROQ_API_KEY)
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model=GROQ_MODEL,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Error querying Groq: {e}")
        raise e

def clean_json_string(response_text: str) -> str:
    """Cleans code blocks or other wrapper text around JSON from the response."""
    # Find JSON structure in the text
    match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if match:
        return match.group(0)
    return response_text

def generate_diagnosis(
    problem_title: str,
    code: str,
    language: str,
    verdict: str,
    error_details: str = None,
    test_cases: list = None
) -> dict:
    """
    Sends problem details, submitted code, and failure details to the LLM agent.
    Returns a dictionary containing {category, explanation, suggested_action}.
    """
    system_prompt = (
        "You are an expert Data Structures and Algorithms (DSA) Tutor. "
        "Your task is to diagnose the root cause of a user's code submission failure on LeetCode. "
        "You must analyze the code, the verdict, and the failing test cases or error messages conceptually.\n\n"
        "Categorize the failure into EXACTLY one of these categories:\n"
        "- 'wrong_approach': The overall algorithmic design is incorrect (e.g. using Greedy where Dynamic Programming is required).\n"
        "- 'implementation_bug': The overall approach is correct, but there is a coding bug (e.g., fencepost/off-by-one errors, wrong pointer updates, typos).\n"
        "- 'edge_case_miss': The code passes general cases but fails on empty input, single element, negative numbers, duplicates, or extreme sizes.\n"
        "- 'complexity_issue': The code is correct but too slow or uses too much memory, leading to Time Limit Exceeded (TLE) or Out Of Memory (OOM).\n"
        "- 'unclear': Compilation errors or syntax issues that prevent execution.\n\n"
        "Provide a plain-language explanation of the conceptual issue (DO NOT just repeat line numbers or restate the raw test failure. "
        "Explain *why* the logic fails or under what conditions it breaks. Be concise but deep).\n\n"
        "Provide a suggested next action (e.g., 'Try dry running on [3, 1, 2] to see where the pointers diverge', "
        "'Step down to an Easy problem on Sliding Window', or 'Recall how to handle duplicates in sorted arrays').\n\n"
        "You MUST respond in strict JSON format with exactly three keys:\n"
        '{\n'
        '  "category": "wrong_approach" | "implementation_bug" | "edge_case_miss" | "complexity_issue" | "unclear",\n'
        '  "explanation": "Your detailed explanation here.",\n'
        '  "suggested_action": "Your recommended action here."\n'
        '}'
    )

    # Format test case info
    test_cases_str = ""
    if test_cases:
        for idx, tc in enumerate(test_cases):
            test_cases_str += f"Test Case {idx+1}:\n"
            if "input" in tc:
                test_cases_str += f"  Input: {tc['input']}\n"
            if "expected" in tc:
                test_cases_str += f"  Expected Output: {tc['expected']}\n"
            if "actual" in tc:
                test_cases_str += f"  Actual Output: {tc['actual']}\n"
    else:
        test_cases_str = "None provided"

    user_prompt = (
        f"Problem: {problem_title}\n"
        f"Language: {language}\n"
        f"Verdict: {verdict}\n"
        f"Error/Stderr details: {error_details or 'None'}\n"
        f"Failing Test Case Info:\n{test_cases_str}\n\n"
        f"Submitted Code:\n```\n{code}\n```\n\n"
        "Please diagnose the root cause of this failure and respond in the requested JSON format."
    )

    # Try Ollama (if Groq key is not configured, or if Ollama is preferred)
    use_groq = GROQ_API_KEY is not None and len(GROQ_API_KEY.strip()) > 0
    
    response_text = ""
    for attempt in range(2): # Simple retry logic
        try:
            if use_groq:
                print(f"Querying Groq using model {GROQ_MODEL}...")
                response_text = query_groq(user_prompt, system_prompt)
            else:
                print(f"Querying Ollama using model {OLLAMA_MODEL}...")
                response_text = query_ollama(user_prompt, system_prompt)

            cleaned_response = clean_json_string(response_text)
            parsed = json.loads(cleaned_response)
            
            # Basic key validation
            if all(key in parsed for key in ["category", "explanation", "suggested_action"]):
                # Map categories safely
                valid_categories = ["wrong_approach", "implementation_bug", "edge_case_miss", "complexity_issue", "unclear"]
                if parsed["category"] not in valid_categories:
                    parsed["category"] = "unclear"
                return {
                    "root_cause_category": parsed["category"],
                    "explanation": parsed["explanation"],
                    "suggested_action": parsed["suggested_action"]
                }
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}. Raw response: {response_text}")
            if attempt == 1:
                break
                
    # Final fallback if LLM queries fail or return invalid JSON
    return {
        "root_cause_category": "unclear",
        "explanation": "The tutor could not parse a structured explanation from the local agent. Please check your submission or try again.",
        "suggested_action": "Check code syntax and try resubmitting, or ensure Ollama is running."
    }


def query_llm(prompt: str, system_prompt: str) -> str:
    """Queries Groq if key is set, otherwise falls back to local Ollama."""
    use_groq = GROQ_API_KEY is not None and len(GROQ_API_KEY.strip()) > 0
    if use_groq:
        return query_groq(prompt, system_prompt)
    else:
        return query_ollama(prompt, system_prompt)


def query_llm_json(prompt: str, system_prompt: str, default_fallback: dict) -> dict:
    """Queries LLM and ensures response is parsed as a valid JSON dictionary."""
    for attempt in range(2):
        try:
            response_text = query_llm(prompt, system_prompt)
            cleaned = clean_json_string(response_text)
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except Exception as e:
            print(f"LLM JSON query attempt {attempt + 1} failed: {e}")
    return default_fallback


def generate_approach_critique(
    problem_title: str,
    code: str,
    language: str,
    constraints: list = None
) -> dict:
    """Checks the user's approach and suggests optimizations if applicable."""
    system_prompt = (
        "You are an expert DSA Tutor. Analyze the user's approach for the given problem.\n"
        "Check if the approach is optimal or can be optimized (e.g. O(N^2) time to O(N) or O(N log N)).\n"
        "You MUST respond in strict JSON format with exactly five keys:\n"
        "{\n"
        '  "is_optimal": true | false,\n'
        '  "current_complexity": "e.g., O(N^2) time, O(1) space",\n'
        '  "optimal_complexity": "e.g., O(N) time, O(N) space",\n'
        '  "feedback": "Critique their approach in 2-3 sentences. Tell them if it\'s good or if there is a better way.",\n'
        '  "alternative_approach": "Briefly describe the optimal approach steps."\n'
        "}"
    )

    constraints_str = "\n".join(constraints) if constraints else "None provided"
    user_prompt = (
        f"Problem: {problem_title}\n"
        f"Language: {language}\n"
        f"Constraints:\n{constraints_str}\n\n"
        f"User's Code:\n```\n{code}\n```\n\n"
        "Please analyze this code and return the requested JSON."
    )

    fallback = {
        "is_optimal": False,
        "current_complexity": "Unknown",
        "optimal_complexity": "Unknown",
        "feedback": "Could not generate approach feedback. Please try again.",
        "alternative_approach": "Review standard solutions on the LeetCode solutions tab."
    }

    return query_llm_json(user_prompt, system_prompt, fallback)


def generate_hint(
    problem_title: str,
    code: str,
    language: str,
    constraints: list = None
) -> dict:
    """Provides a progressive, conceptual hint without giving away the direct code."""
    system_prompt = (
        "You are an expert DSA Tutor. Provide a progressive, conceptual hint to help the user solve the problem.\n"
        "Do NOT provide the direct code solution or code snippets. Instead, explain the conceptual trick, ask guiding questions, or explain the logic.\n"
        "You MUST respond in strict JSON format with exactly one key:\n"
        "{\n"
        '  "hint": "Your progressive hint here."\n'
        "}"
    )

    constraints_str = "\n".join(constraints) if constraints else "None provided"
    user_prompt = (
        f"Problem: {problem_title}\n"
        f"Language: {language}\n"
        f"Constraints:\n{constraints_str}\n\n"
        f"User's Current Code:\n```\n{code}\n```\n\n"
        "Please give me a progressive hint to help me move forward."
    )

    fallback = {
        "hint": "Try writing down the problem requirements and dry-running a small testcase on paper."
    }

    return query_llm_json(user_prompt, system_prompt, fallback)


def analyze_edge_cases(
    problem_title: str,
    code: str,
    language: str,
    constraints: list = None
) -> dict:
    """Identifies potential edge cases and critiques the constraints."""
    system_prompt = (
        "You are an expert DSA Tutor. Identify 3-4 potential edge cases for the given problem.\n"
        "Evaluate whether the user's code handles them properly, and explain the constraints' implications.\n"
        "You MUST respond in strict JSON format with exactly two keys:\n"
        "{\n"
        '  "edge_cases": [\n'
        '    {"case": "Edge case description", "handled": true / false, "suggestion": "How to handle it."}\n'
        '  ],\n'
        '  "constraints_critique": "Explain what the constraints mean for performance (e.g. an O(N^2) solution will TLE because N is up to 10^5)."\n'
        "}"
    )

    constraints_str = "\n".join(constraints) if constraints else "None provided"
    user_prompt = (
        f"Problem: {problem_title}\n"
        f"Language: {language}\n"
        f"Constraints:\n{constraints_str}\n\n"
        f"User's Code:\n```\n{code}\n```\n\n"
        "Please analyze the edge cases and constraints."
    )

    fallback = {
        "edge_cases": [
            {"case": "Empty or single-element inputs", "handled": False, "suggestion": "Ensure you handle minimal inputs."},
            {"case": "Extremely large inputs", "handled": False, "suggestion": "Check for performance bottlenecks."}
        ],
        "constraints_critique": "Please review problem constraints to ensure your time complexity is within limits."
    }

    return query_llm_json(user_prompt, system_prompt, fallback)


def answer_custom_question(
    problem_title: str,
    code: str,
    language: str,
    constraints: list = None,
    question: str = ""
) -> dict:
    """Answers a user's custom question about their code or the problem."""
    system_prompt = (
        "You are an expert DSA Tutor. Answer the user's specific question about their code or the problem.\n"
        "Be clear, educational, and concise. You may reference their code and constraints.\n"
        "You MUST respond in strict JSON format with exactly one key:\n"
        "{\n"
        '  "answer": "Your detailed answer here."\n'
        "}"
    )

    constraints_str = "\n".join(constraints) if constraints else "None provided"
    user_prompt = (
        f"Problem: {problem_title}\n"
        f"Language: {language}\n"
        f"Constraints:\n{constraints_str}\n\n"
        f"User's Code:\n```\n{code}\n```\n\n"
        f"User's Question: {question}\n\n"
        "Please answer this question and return the requested JSON."
    )

    fallback = {
        "answer": "I'm sorry, I couldn't process your question right now. Please try asking again."
    }

    return query_llm_json(user_prompt, system_prompt, fallback)

