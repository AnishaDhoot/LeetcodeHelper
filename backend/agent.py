from pathlib import Path
import os
import json
import re
from dotenv import load_dotenv
import ollama
from groq import Groq

# Load environment variables explicitly from backend dir and root dir
_backend_dir = Path(__file__).resolve().parent
_root_dir = _backend_dir.parent

load_dotenv(dotenv_path=_backend_dir / ".env")
load_dotenv(dotenv_path=_root_dir / ".env")

def get_groq_api_key() -> str:
    key = os.getenv("GROQ_API_KEY", "")
    return key.strip() if key else ""

def get_groq_model() -> str:
    return os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

def get_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

def query_ollama(prompt: str, system_prompt: str) -> str:
    """Queries the local Ollama instance."""
    try:
        model = get_ollama_model()
        response = ollama.chat(
            model=model,
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
    api_key = get_groq_api_key()
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set")
    
    client = Groq(api_key=api_key)
    target_model = get_groq_model()
    candidate_models = [target_model, "openai/gpt-oss-20b", "qwen/qwen3.6-27b", "groq/compound-mini", "groq/compound", "openai/gpt-oss-120b"]
    
    # Remove duplicates while preserving order
    seen = set()
    models_to_try = [m for m in candidate_models if not (m in seen or seen.add(m))]

    last_exception = None
    for model in models_to_try:
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                model=model,
                temperature=0.2,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            err_msg = str(e)
            print(f"Error querying Groq with model '{model}': {e}")
            last_exception = e
            # Only retry next model if it's a model not found / 404 error
            if "model_not_found" in err_msg or "404" in err_msg or "does not exist" in err_msg:
                continue
            else:
                raise e

    if last_exception:
        raise last_exception

def clean_json_string(response_text: str) -> str:
    """Cleans code blocks or other wrapper text around JSON from the response."""
    text = response_text.strip()
    # Remove markdown code block syntax if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    # Find JSON structure in the text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        return match.group(0)
    return text

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

    response_text = ""
    for attempt in range(2): # Simple retry logic
        try:
            response_text = query_llm(user_prompt, system_prompt)
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
    """Queries Groq if key is set, falling back to local Ollama if Groq fails or is unconfigured."""
    api_key = get_groq_api_key()
    if api_key:
        try:
            print(f"Querying Groq using model {get_groq_model()}...")
            return query_groq(prompt, system_prompt)
        except Exception as e:
            print(f"Groq query failed ({e}). Falling back to Ollama ({get_ollama_model()})...")
            return query_ollama(prompt, system_prompt)
    else:
        print(f"No GROQ_API_KEY found. Querying Ollama using model {get_ollama_model()}...")
        return query_ollama(prompt, system_prompt)


def repair_json_string(s: str) -> str:
    """Attempts lightweight repair on invalid JSON strings produced by LLMs."""
    # Fix trailing commas before closing braces/brackets
    s = re.sub(r",\s*([\]}])", r"\1", s)
    return s


def query_llm_json(prompt: str, system_prompt: str, default_fallback: dict) -> dict:
    """Queries LLM and ensures response is parsed as a valid JSON dictionary."""
    for attempt in range(2):
        try:
            response_text = query_llm(prompt, system_prompt)
            cleaned = clean_json_string(response_text)
            try:
                parsed = json.loads(cleaned)
            except Exception:
                repaired = repair_json_string(cleaned)
                parsed = json.loads(repaired)

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
    """Provides an actionable, progressive, conceptual hint without giving away the raw code syntax."""
    system_prompt = (
        "You are an expert DSA Tutor. Provide an insightful, highly actionable conceptual hint for the given problem.\n"
        "Explain the core algorithmic pattern, key invariant, or mathematical observation required to solve it efficiently.\n"
        "You MUST respond in strict JSON format with exactly one key:\n"
        "{\n"
        '  "hint": "Your detailed, actionable conceptual hint here."\n'
        "}"
    )

    constraints_str = "\n".join(constraints) if constraints else "None provided"
    user_prompt = (
        f"Problem: {problem_title}\n"
        f"Language: {language}\n"
        f"Constraints:\n{constraints_str}\n\n"
        f"User's Current Code:\n```\n{code}\n```\n\n"
        "Please give me a clear, actionable hint to guide me forward."
    )

    fallback = {
        "hint": "Analyze the constraints to determine the target complexity, and look for redundant calculations in your current approach."
    }

    return query_llm_json(user_prompt, system_prompt, fallback)


def generate_levelled_hint(
    problem_title: str,
    code: str,
    language: str,
    level: int,
    constraints: list = None
) -> dict:
    """Provides a progressive, conceptual hint at the requested level (1, 2, or 3)
    without giving away direct code syntax.
    """
    if level == 1:
        level_instruction = (
            "Level 1 (Core Concept & Pattern Insight): Explain the main intuition and structural insight needed for this problem. "
            "Identify what invariant, state relationship, or mathematical observation is key, and explain why naive or brute-force intuition breaks down."
        )
    elif level == 2:
        level_instruction = (
            "Level 2 (Optimal Algorithm & Data Structure Strategy): Explicitly specify the optimal technique "
            "(e.g. Two Pointers, Monotonic Stack, Sliding Window, Hash Map, Binary Search, DP transition) "
            "and explain how to organize and process the data to achieve the optimal time and space complexity."
        )
    else:
        level_instruction = (
            "Level 3 (Detailed Pseudocode & Step-by-Step Logic Walkthrough): Provide a clear, step-by-step logic breakdown "
            "or pseudocode. Detail the state variable initialization, loop boundary conditions, update rules, and edge checks "
            "so the user can immediately implement the solution. Do NOT output raw executable syntax for a specific programming language."
        )

    system_prompt = (
        "You are an expert DSA Tutor providing progressive hints for a user solving a LeetCode problem.\n"
        f"{level_instruction}\n\n"
        "Provide a clear, educational, and actionable response.\n"
        "You MUST respond in strict JSON format with exactly three keys:\n"
        "{\n"
        '  "hint": "Your progressive hint text here.",\n'
        '  "level": int,\n'
        '  "has_next": true | false\n'
        "}"
    )

    constraints_str = "\n".join(constraints) if constraints else "None provided"
    user_prompt = (
        f"Problem: {problem_title}\n"
        f"Language: {language}\n"
        f"Constraints:\n{constraints_str}\n\n"
        f"User's Current Code:\n```\n{code}\n```\n\n"
        f"Please give me a Level {level} progressive hint."
    )

    fallback = {
        "hint": "Dry-run a small example on paper and trace how state variables change across iterations.",
        "level": level,
        "has_next": level < 3
    }

    result = query_llm_json(user_prompt, system_prompt, fallback)
    try:
        hint_val = result.get("hint", fallback["hint"])
        level_val = int(result.get("level", level))
        has_next_val = bool(result.get("has_next", level < 3)) if level_val < 3 else False
    except Exception:
        hint_val = fallback["hint"]
        level_val = level
        has_next_val = level < 3

    return {
        "hint": hint_val,
        "level": level_val,
        "has_next": has_next_val
    }



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


def generate_explain_back_check(
    code: str,
    language: str,
    user_explanation: str
) -> dict:
    """
    Verifies whether the user's plain-English explanation actually matches the implementation in their code (Tier 3.2).
    Returns {"matches": bool, "discrepancy_note": str | None}.
    """
    system_prompt = (
        "You are an expert DSA Tutor. The user has submitted a working code solution in the specified programming language "
        "and provided a brief self-explanation of their approach.\n"
        "Your task is to check if their explanation accurately reflects the logic and algorithm used in their code.\n"
        "You MUST respond in strict JSON format with exactly two keys:\n"
        "{\n"
        '  "matches": true | false,\n'
        '  "discrepancy_note": "Null if matches is true, or a brief explanation if their explanation diverges from what the code actually does."\n'
        "}"
    )

    user_prompt = (
        f"Language: {language}\n"
        f"User's Code:\n```\n{code}\n```\n\n"
        f"User's Self-Explanation: \"{user_explanation}\"\n\n"
        "Please check if the explanation matches the code."
    )

    return query_llm_json(user_prompt, system_prompt, fallback)


def evaluate_mock_approach(problem_title: str, approach_text: str) -> dict:
    """Evaluates user's verbal strategy for a mock interview question."""
    text_clean = (approach_text or "").strip().lower()

    invalid_phrases = ["idk", "i don't know", "dont know", "no idea", "asdf", "skip", "pass", "help", "dunno", "na", "n/a", "none"]
    is_non_answer = len(text_clean) < 8 or any(text_clean == p or text_clean.startswith(p + " ") or text_clean.endswith(" " + p) for p in invalid_phrases)

    if is_non_answer:
        return {
            "approved": False,
            "feedback": "Interviewer: 'Please describe a specific algorithm approach (e.g. Two Pointers, Hash Map, Sliding Window, BFS/DFS, DP) and your estimated time & space complexity before unlocking the code editor.'"
        }

    system_prompt = (
        "You are a Senior Technical Interviewer at a top tech company evaluating a candidate's verbal strategy before coding.\n"
        "Review the candidate's explanation for the problem:\n"
        "- As long as the candidate proposes a plausible algorithm idea, data structure, or technique (e.g., two pointers, hash map, sliding window, binary search, bfs/dfs, dp, greedy, recursion, sorting): return approved=true with brief encouraging commentary.\n"
        "- Only return approved=false if the candidate states they don't know, provides complete nonsense, or gives no strategy at all.\n\n"
        "Return ONLY a JSON object: {\"approved\": boolean, \"feedback\": \"Interviewer commentary...\"}"
    )
    prompt = f"Problem: {problem_title}\nCandidate Approach: {approach_text}"

    fallback = {
        "approved": True,
        "feedback": f"Interviewer: 'Strategy received! Using {approach_text[:60]}... is a valid approach. Editor is UNLOCKED. Good luck!'"
    }

    return query_llm_json(prompt, system_prompt, fallback)


def generate_mock_scorecard(company: str, duration_seconds: int, questions_data: list) -> dict:
    """Generates an interview scorecard based on user performance across 3 mock questions."""
    system_prompt = (
        "You are a Lead Software Engineering Interviewer evaluating a candidate's full 3-question technical interview. "
        "Return ONLY a JSON object with keys:\n"
        "{\n"
        '  "verdict": "Strong Hire" | "Hire" | "Weak Lean" | "Needs Practice",\n'
        '  "strategy_score": 1-5,\n'
        '  "code_quality_score": 1-5,\n'
        '  "time_management_score": 1-5,\n'
        '  "overall_summary": "Concise executive summary of performance",\n'
        '  "strengths": ["list of 2-3 key strengths"],\n'
        '  "areas_for_improvement": ["list of 2-3 improvement areas"]\n'
        "}"
    )
    prompt = f"Company: {company or 'General Tech'}\nTime Spent: {duration_seconds // 60} minutes\nQuestions & Approaches: {json.dumps(questions_data)}"
    
    fallback = {
        "verdict": "Hire",
        "strategy_score": 4,
        "code_quality_score": 4,
        "time_management_score": 4,
        "overall_summary": "Solid technical communication and structured problem solving across all questions.",
        "strengths": ["Clear verbal strategy before coding", "Effective algorithm choices"],
        "areas_for_improvement": ["Practice edge case validation before submitting", "Optimize space complexity where possible"]
    }
    
    return query_llm_json(prompt, system_prompt, fallback)



