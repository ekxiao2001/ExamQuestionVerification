# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository implements an **Exam Question Verification and Correction System** that uses AI agents to verify and fix exam questions. The system consists of two main components:

1. **Agent Runtime** (port 8021): A conversational agent interface powered by AgentScope
2. **FastAPI Server** (port 8022): A REST API providing verification and correction endpoints

## Project Structure

```
src/ExamQuestionVerification/
├── agent_runtime.py           # AgentScope-based agent runtime (conversational interface)
├── eqv_agent.py               # Agent implementation with tools
├── exam_question_verification.py  # Core verification logic
├── fastapi_server.py          # FastAPI REST API server
├── schemas.py                 # Pydantic models for API requests/responses
├── prompts.py                 # LLM prompt templates
├── conf.yaml                  # Configuration file
└── README.md                  # Component documentation
```

## Development Commands

### Running the Application

**Using Docker Compose (recommended)**:
```bash
# Pull sandbox images and deploy all services
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**Running locally**:
```bash
# Install dependencies
uv sync --frozen --no-dev

# Run agent runtime (conversational interface)
uv run src/ExamQuestionVerification/agent_runtime.py

# Run FastAPI server (in another terminal)
uv run src/ExamQuestionVerification/fastapi_server.py

# Or run both via supervisor
supervisord -c supervisord.conf
```

**Single file execution**:
```bash
# Test core verification logic
uv run src/ExamQuestionVerification/exam_question_verification.py
```

### Key Configuration Files

- **conf.yaml**: Model configuration (LLM binding, API keys, ports)
- **.env**: Environment variables for deployment
- **docker-compose.yml**: Service orchestration
- **supervisord.conf**: Process management for local runs

## Architecture

### Core Components

1. **ExamQuestionVerification** (src/ExamQuestionVerification/exam_question_verification.py:20)
   - Main verification engine with two implementations:
     - `main()`: Direct verification + correction flow
     - `agent_main()`: Uses ReActAgent with toolkit integration
   - Methods: `verify_exam_question()`, `fix_exam_question()`

2. **ExamQuestionVerificationAgent** (src/ExamQuestionVerification/eqv_agent.py:187)
   - AgentScope-based implementation with three tools:
     - `verify_exam_question_tool`: Standalone verification
     - `fix_exam_question_tool`: Standalone correction
     - `verify_and_fix_exam_question_tool`: Combined operation
   - Uses Runner pattern for deployment

3. **FastAPI Server** (src/ExamQuestionVerification/fastapi_server.py:20)
   - Three main endpoints:
     - `POST /api/v1/verify`: Verify question compliance
     - `POST /api/v1/fix`: Fix question based on verification result
     - `POST /api/v1/verify-and-fix`: Combined verification + correction
   - Provides interactive API docs at `/docs`

### Supported Question Types

The system validates different question types with specific criteria (src/ExamQuestionVerification/prompts.py):
- **Single Choice** (单选题): 4 options, single correct answer
- **Multi Choice** (多选题): Multiple correct answers
- **Fill Blank** (填空题): Deterministic answers
- **Brief Answer** (简答题): Paragraph-length responses
- **Calculation** (计算题): Step-by-step solvable

### Model Support

The system supports two LLM backends (configurable in conf.yaml):
- **DeepSeek** (default): Uses OpenAI-compatible API
- **DashScope**: Alibaba's Qwen models

## API Usage

### Verification
```python
POST /api/v1/verify
{
  "question": "...",
  "answer": "...",
  "question_type": "单选题",
  "knowledge_point": "...",
  "knowledge_point_description": "...",
  "extra_requirement": "..."
}
```

### Combined Verification + Fix
```python
POST /api/v1/verify-and-fix
{
  "exam_question": { ... },
  "max_fix_attempts": 3  # 1-5 attempts
}
```

## Configuration

**Model Configuration** (conf.yaml:1-5):
- `LLM_BINDING`: "deepseek" or "dashscope"
- `MODEL_NAME`: Model identifier (e.g., "deepseek-chat", "qwen-plus")
- `API_KEY`: LLM API credentials
- `BASE_URL`: API base URL

**Service Ports** (conf.yaml:11-18):
- Agent Runtime: 8021 (docker-compose: 8021)
- FastAPI Server: 8022 (docker-compose: 8022)

## Deployment Architecture

The system runs with multiple containers (docker-compose.yml):
1. **agents_server**: Main application (built from Dockerfile)
2. **runtime_sandbox_base**: Base sandbox environment (port 8011)
3. **runtime_sandbox_filesystem**: File system sandbox (port 8012)
4. **runtime_sandbox_browser**: Browser automation sandbox (port 8013)

Note: Sandbox containers are configured but currently not actively used in the agent implementation (see commented code in eqv_agent.py:220-233).

## Testing

The repository includes a Jupyter notebook at `src/ExamQuestionVerification/demo.ipynb` for interactive testing and demonstrations.

## Troubleshooting

- **Port conflicts**: Ensure ports 8761, 8762, 8011-8013 are available
- **API key errors**: Verify API keys in conf.yaml or .env match your LLM provider
- **Model loading failures**: Check model name and base URL configuration
- **Docker issues**: Pull required images first (see README.md:3-15)

## Key Implementation Details

- **Agent Pattern**: Uses ReActAgent from AgentScope with InMemoryMemory
- **Tool Integration**: Functions wrapped as tools using `@function_tool` decorator
- **Async Operations**: All LLM calls are async; sync wrappers use ThreadPoolExecutor
- **Structured Output**: Pydantic models ensure type safety
- **Process Management**: Supervisor handles both agent runtime and FastAPI server
- **CORS Enabled**: FastAPI allows all origins for browser-based clients
