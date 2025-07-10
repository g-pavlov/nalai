# Unit Tests

This directory contains comprehensive unit tests for the API Assistant project, organized to mirror the structure of the source code packages.

## Test Structure

The test structure reflects the package organization in `src/api_assistant/`:

```
tests/unit/
├── conftest.py                 # Shared fixtures and configuration
├── test_data/                  # Externalized test data (YAML files)
│   ├── agent_test_cases.yaml
│   ├── http_tools_test_cases.yaml
│   ├── model_service_test_cases.yaml
│   └── chat_history_test_cases.yaml
├── core/                       # Tests for core package
│   ├── __init__.py
│   ├── test_agent.py          # APIAssistant tests
│   ├── test_workflow.py       # Workflow creation tests
│   ├── test_interrupts.py     # Human review processing tests
│   └── test_schemas.py        # Data model validation tests
├── services/                   # Tests for services package
│   ├── __init__.py
│   └── test_model_service.py  # Model service tests
├── tools/                      # Tests for tools package
│   ├── __init__.py
│   └── test_http_requests.py  # HTTP tools tests
├── utils/                      # Tests for utils package
│   ├── __init__.py
│   └── test_chat_history.py   # Chat history utilities tests
└── test_logging_config.py     # Logging configuration tests
```

## Test Design Principles

### 1. Package Structure Reflection
- Test modules are organized to mirror the source code package structure
- Each package has its own test directory with corresponding test files
- Test file names reflect the module being tested (without package prefix)

### 2. Table-Style Tests with Externalized Data
- Test cases are defined in YAML files in `test_data/`
- Tests use `@pytest.mark.parametrize` for table-driven testing
- Test data is loaded via fixtures to minimize boilerplate

### 3. Comprehensive Mocking
- All external dependencies are mocked
- Tests focus on unit behavior, not integration
- Mocks are configured to verify correct interactions

### 4. Pytest Best Practices
- Extensive use of fixtures for test setup
- Shared fixtures in `conftest.py`
- Proper test isolation and cleanup
- Custom markers for test categorization

## Running Tests

### Run all unit tests:
```bash
pytest tests/unit/
```

### Run tests for a specific package:
```bash
pytest tests/unit/core/
pytest tests/unit/services/
pytest tests/unit/tools/
pytest tests/unit/utils/
```

### Run specific test modules:
```bash
pytest tests/unit/core/test_agent.py
pytest tests/unit/services/test_model_service.py
```

### Run tests with specific markers:
```bash
pytest tests/unit/ -m unit
pytest tests/unit/ -m "not slow"
```

## Test Data Organization

Test data is externalized in YAML files to:
- Minimize test code boilerplate
- Make test cases easy to read and modify
- Enable data-driven testing patterns
- Separate test logic from test data

### Test Data Files:
- `agent_test_cases.yaml`: APIAssistant functionality test cases
- `http_tools_test_cases.yaml`: HTTP tools validation and processing
- `model_service_test_cases.yaml`: Model service configuration and initialization
- `chat_history_test_cases.yaml`: Chat history utilities and token management

## Fixtures

Shared fixtures are defined in `conftest.py`:

- `mock_config`: Mock configuration for testing
- `mock_model`: Mock language model
- `mock_http_response`: Mock HTTP responses
- `sample_messages`: Sample conversation messages
- `sample_api_summaries`: Sample API documentation
- `test_data_helper`: Utility class for creating test data

## Test Coverage

The test suite covers:

### Core Package
- **Agent**: Initialization, API selection, workflow actions, model response generation
- **Workflow**: Graph creation, node/edge management, compilation
- **Interrupts**: Human review processing, action handling
- **Schemas**: Data model validation, type checking

### Services Package
- **Model Service**: Model initialization, configuration, context window management
- **API Docs Service**: API specification loading and processing

### Tools Package
- **HTTP Tools**: Request validation, header processing, response handling
- **Toolkit**: Tool management and safety checking

### Utils Package
- **Chat History**: Token counting, conversation trimming/compression
- **Logging**: Configuration and setup

## Adding New Tests

When adding new tests:

1. **Follow the package structure**: Place tests in the appropriate package directory
2. **Use externalized data**: Add test cases to YAML files in `test_data/`
3. **Leverage shared fixtures**: Use fixtures from `conftest.py` when possible
4. **Mock external dependencies**: Ensure tests are truly unit tests
5. **Use table-driven testing**: Parameterize tests with multiple test cases
6. **Add proper documentation**: Include docstrings explaining test purpose

## Test Quality Standards

- **Isolation**: Tests should not depend on each other
- **Deterministic**: Tests should produce consistent results
- **Fast**: Unit tests should run quickly (< 1 second each)
- **Comprehensive**: Cover normal cases, edge cases, and error conditions
- **Readable**: Test names and structure should be self-documenting 