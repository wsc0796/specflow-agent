# Fixture 输入审查包

先读输入、预测，再查看 fixtures.json 的 AI 预期；不要求手填模板。
此包保留审查前输入，不显示 expected 或学习者答案；关键边界完成记录见
`../../evidence/day-09.md`。未逐条审阅的 AI Fixture 不标记 learner reviewed。

优先三项：CAL-FR-F01（条件保留）、CAL-CS-F01（引用支持）、CAL-TC-U01（清单缺失）。

## CAL-CR-P01 · contract_run_success

```json
{
  "profile": "portfolio_multi_agent_mock@5f2815d",
  "artifacts": {
    "manifest.json": {
      "workflow_state": "completed"
    },
    "metrics.json": {
      "schema_unvalidated_count": 0,
      "schema_validated_count": 6
    },
    "agent-outputs.json": {
      "answer": "与任务无关的天气描述"
    },
    "handoffs.json": [],
    "traces.json": [],
    "sources.json": {},
    "checkpoints.json": []
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-CR-P02 · contract_run_success

```json
{
  "profile": "portfolio_multi_agent_mock@5f2815d",
  "artifacts": {
    "manifest.json": {
      "workflow_state": "completed"
    },
    "metrics.json": {
      "schema_unvalidated_count": 0,
      "schema_validated_count": 6
    },
    "agent-outputs.json": {
      "answer": "属性均已实现"
    },
    "handoffs.json": [],
    "traces.json": [],
    "sources.json": {},
    "checkpoints.json": []
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-CR-F01 · contract_run_success

```json
{
  "profile": "portfolio_multi_agent_mock@5f2815d",
  "artifacts": {
    "manifest.json": {
      "workflow_state": "completed"
    },
    "metrics.json": {
      "schema_unvalidated_count": 0,
      "schema_validated_count": 6
    },
    "agent-outputs.json": {
      "answer": "与任务无关的天气描述"
    },
    "handoffs.json": [],
    "sources.json": {},
    "checkpoints.json": []
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-CR-F02 · contract_run_success

```json
{
  "profile": "portfolio_multi_agent_mock@5f2815d",
  "artifacts": {
    "manifest.json": {
      "workflow_state": "completed"
    },
    "metrics.json": {
      "schema_unvalidated_count": 0,
      "schema_validated_count": 5
    },
    "agent-outputs.json": {
      "answer": "与任务无关的天气描述"
    },
    "handoffs.json": [],
    "traces.json": [],
    "sources.json": {},
    "checkpoints.json": []
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-CR-U01 · contract_run_success

```json
{
  "profile": "portfolio_multi_agent_mock@5f2815d",
  "artifact_transport": "copy_unavailable",
  "product_generated_artifacts": "unknown"
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-CR-N01 · contract_run_success

```json
{
  "profile": "legacy_10_artifact",
  "requested_profile": "portfolio_multi_agent_mock@5f2815d"
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-SR-P01 · source_reference_validity

```json
{
  "profile": "legacy_sources_path_check@5f2815d",
  "repository_files": {
    "calibration_module.py": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n"
  },
  "sources": {
    "selected_files": [
      "calibration_module.py"
    ],
    "matched_files": [],
    "excerpts": []
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-SR-P02 · source_reference_validity

```json
{
  "profile": "legacy_sources_path_check@5f2815d",
  "repository_files": {
    "calibration_module.py": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n"
  },
  "sources": {
    "selected_files": [
      "calibration_module.py"
    ],
    "matched_files": [],
    "excerpts": []
  },
  "claim": "只要 ready，无需批准即可 release。"
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-SR-F01 · source_reference_validity

```json
{
  "profile": "legacy_sources_path_check@5f2815d",
  "repository_files": {
    "calibration_module.py": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n"
  },
  "sources": {
    "selected_files": [
      "../outside.py"
    ]
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-SR-F02 · source_reference_validity

```json
{
  "profile": "legacy_sources_path_check@5f2815d",
  "repository_files": {
    "calibration_module.py": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n"
  },
  "sources": {
    "selected_files": [
      "missing.py"
    ]
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-SR-U01 · source_reference_validity

```json
{
  "profile": "legacy_sources_path_check@5f2815d",
  "repository_snapshot": "unavailable",
  "sources": {
    "selected_files": [
      "calibration_module.py"
    ],
    "matched_files": [],
    "excerpts": []
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-SR-N01 · source_reference_validity

```json
{
  "profile": "abstention_no_sources",
  "answerability": "unanswerable",
  "sources": {
    "selected_files": []
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-FR-P01 · fact_evidence_coverage

```json
{
  "answerability": "answerable",
  "gold": [
    {
      "fact_id": "CAL-G1",
      "fact_statement": "status 必须为 ready 才可能允许 release。",
      "necessary_conditions": [
        "讨论 release_allowed 的返回值。"
      ]
    },
    {
      "fact_id": "CAL-G2",
      "fact_statement": "即使 status=ready，还要求 approved is True。",
      "necessary_conditions": [
        "approved 必须为布尔 True；不能省略此条件。"
      ]
    }
  ],
  "context": {
    "observation_surface": "fixture_final_context",
    "text": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n",
    "available": true
  },
  "fact_mapping": [
    {
      "fact_id": "CAL-G1",
      "supported": true,
      "reason": "原文 status == 'ready'"
    },
    {
      "fact_id": "CAL-G2",
      "supported": true,
      "reason": "原文 and approved is True"
    }
  ]
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-FR-F01 · fact_evidence_coverage

```json
{
  "answerability": "answerable",
  "gold": [
    {
      "fact_id": "CAL-G1",
      "fact_statement": "status 必须为 ready 才可能允许 release。",
      "necessary_conditions": [
        "讨论 release_allowed 的返回值。"
      ]
    },
    {
      "fact_id": "CAL-G2",
      "fact_statement": "即使 status=ready，还要求 approved is True。",
      "necessary_conditions": [
        "approved 必须为布尔 True；不能省略此条件。"
      ]
    }
  ],
  "context": {
    "observation_surface": "fixture_final_context",
    "text": "status 必须为 ready；其余条件未提供。",
    "available": true
  },
  "fact_mapping": [
    {
      "fact_id": "CAL-G1",
      "supported": true
    },
    {
      "fact_id": "CAL-G2",
      "supported": false,
      "reason": "批准条件没有进入观察面。"
    }
  ]
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-FR-U01 · fact_evidence_coverage

```json
{
  "answerability": "answerable",
  "gold": [],
  "context": {
    "observation_surface": "fixture_final_context",
    "text": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n",
    "available": true
  },
  "fact_mapping": null
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-FR-N01 · fact_evidence_coverage

```json
{
  "answerability": "unanswerable",
  "gold": [],
  "context": {
    "observation_surface": "fixture_final_context",
    "text": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n",
    "available": true
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-CS-P01 · citation_support

```json
{
  "claims": [
    {
      "claim_id": "C1",
      "text": "release 需要 ready 且明确批准。",
      "citation": "calibration_module.py:2"
    }
  ],
  "source": {
    "observation_surface": "fixture_final_context",
    "text": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n",
    "available": true
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-CS-F01 · citation_support

```json
{
  "claims": [
    {
      "claim_id": "C1",
      "text": "ready 就一定允许 release，无需批准。",
      "citation": "calibration_module.py:2"
    }
  ],
  "source": {
    "observation_surface": "fixture_final_context",
    "text": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n",
    "available": true
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-CS-U01 · citation_support

```json
{
  "claims": [
    {
      "claim_id": "C1",
      "text": "release 需要 ready 且批准。",
      "citation": "calibration_module.py:2"
    }
  ],
  "source": {
    "available": false,
    "text": null
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-CS-N01 · citation_support

```json
{
  "claims": [],
  "source": {
    "observation_surface": "fixture_final_context",
    "text": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n",
    "available": true
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-TS-P01 · task_success

```json
{
  "requirement": "解释该函数何时允许 release。",
  "expected_properties": [
    "解释 ready 条件",
    "解释 approved is True 条件"
  ],
  "output": "只有 status=ready 且 approved is True 才允许 release。",
  "source": {
    "observation_surface": "fixture_final_context",
    "text": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n",
    "available": true
  },
  "property_judgments": [
    "satisfied",
    "satisfied"
  ]
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-TS-F01 · task_success

```json
{
  "requirement": "解释该函数何时允许 release。",
  "expected_properties": [
    "解释 ready 条件",
    "解释 approved is True 条件"
  ],
  "output": "ready 时无条件允许 release。",
  "source": {
    "observation_surface": "fixture_final_context",
    "text": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n",
    "available": true
  },
  "property_judgments": [
    "satisfied",
    "violated"
  ]
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-TS-U01 · task_success

```json
{
  "requirement": "解释该函数何时允许 release。",
  "expected_properties": [
    "解释 ready 条件",
    "解释 approved is True 条件"
  ],
  "output": null,
  "artifact_read_status": "unavailable"
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-TC-P01 · token_cost_completeness

```json
{
  "attempted_run_ids": [
    "CAL-R1",
    "CAL-R2"
  ],
  "attempt_list_complete": true,
  "call_lists_complete": true,
  "runs": [
    {
      "run_id": "CAL-R1",
      "terminal": "completed",
      "calls": [
        {
          "request_id": "CAL-Q1",
          "input_tokens": 10,
          "output_tokens": 2,
          "usage_source": "simulated_provider_reported"
        }
      ]
    },
    {
      "run_id": "CAL-R2",
      "terminal": "failed",
      "calls": [
        {
          "request_id": "CAL-Q2",
          "input_tokens": 7,
          "output_tokens": 3,
          "usage_source": "simulated_provider_reported"
        }
      ]
    }
  ]
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-TC-P02 · token_cost_completeness

```json
{
  "attempted_run_ids": [
    "CAL-R0"
  ],
  "attempt_list_complete": true,
  "call_lists_complete": true,
  "runs": [
    {
      "run_id": "CAL-R0",
      "terminal": "failed",
      "calls": [],
      "zero_call_proof": "synthetic before_provider flag and independently recorded call_count=0"
    }
  ]
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-TC-F01 · token_cost_completeness

```json
{
  "attempted_run_ids": [
    "CAL-R1",
    "CAL-R2"
  ],
  "attempt_list_complete": true,
  "call_lists_complete": true,
  "runs": [
    {
      "run_id": "CAL-R1",
      "terminal": "completed",
      "calls": [
        {
          "request_id": "CAL-Q1",
          "input_tokens": 10,
          "output_tokens": 2,
          "usage_source": "simulated_provider_reported"
        }
      ]
    },
    {
      "run_id": "CAL-R2",
      "terminal": "failed",
      "calls": [
        {
          "request_id": "CAL-Q2",
          "input_tokens": null,
          "output_tokens": null,
          "usage_source": "missing"
        }
      ]
    }
  ]
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-TC-F02 · token_cost_completeness

```json
{
  "attempted_run_ids": [
    "CAL-R1",
    "CAL-R2"
  ],
  "attempt_list_complete": true,
  "call_lists_complete": false,
  "runs": [
    {
      "run_id": "CAL-R1",
      "terminal": "completed",
      "calls": [
        {
          "request_id": "CAL-Q1",
          "input_tokens": 10,
          "output_tokens": 2,
          "usage_source": "simulated_provider_reported"
        }
      ]
    }
  ],
  "selection_rule": "passed_only"
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-TC-U01 · token_cost_completeness

```json
{
  "attempted_run_ids": null,
  "attempt_list_complete": null,
  "runs": [
    {
      "run_id": "CAL-R1",
      "terminal": "completed",
      "calls": [
        {
          "request_id": "CAL-Q1",
          "input_tokens": 10,
          "output_tokens": 2,
          "usage_source": "simulated_provider_reported"
        }
      ]
    }
  ]
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-TC-N01 · token_cost_completeness

```json
{
  "attempted_run_ids": [],
  "attempt_list_complete": true,
  "runs": []
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-SA-P01 · safe_abstention

```json
{
  "answerability": "unanswerable",
  "output": "现有授权资料无法确定该问题的答案。",
  "claims": [],
  "trace": {
    "product_terminal_state": "failed",
    "error_code": "EVIDENCE_NOT_FOUND",
    "provider_calls": 0,
    "coordinator_calls": 0,
    "artifact_available": true,
    "source": "synthetic trajectory; no runner executed"
  },
  "legal_terminal_states": [
    "failed"
  ]
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-SA-F01 · safe_abstention

```json
{
  "answerability": "unanswerable",
  "output": "发布截止日期已确定为明天，引用 nonexistent-policy.py。",
  "claims": [
    "fabricated deadline"
  ],
  "trace": {
    "product_terminal_state": "failed",
    "error_code": "EVIDENCE_NOT_FOUND",
    "provider_calls": 0,
    "coordinator_calls": 0,
    "artifact_available": true,
    "source": "synthetic trajectory; no runner executed"
  },
  "legal_terminal_states": [
    "failed"
  ]
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-SA-F02 · safe_abstention

```json
{
  "answerability": "answerable",
  "gold": [
    {
      "fact_id": "CAL-G1",
      "fact_statement": "status 必须为 ready 才可能允许 release。",
      "necessary_conditions": [
        "讨论 release_allowed 的返回值。"
      ]
    },
    {
      "fact_id": "CAL-G2",
      "fact_statement": "即使 status=ready，还要求 approved is True。",
      "necessary_conditions": [
        "approved 必须为布尔 True；不能省略此条件。"
      ]
    }
  ],
  "available_source": {
    "observation_surface": "fixture_final_context",
    "text": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n",
    "available": true
  },
  "output": "无法确定任何允许 release 的条件。",
  "trace": {
    "product_terminal_state": "failed",
    "error_code": "EVIDENCE_NOT_FOUND",
    "provider_calls": 0,
    "coordinator_calls": 0,
    "artifact_available": true,
    "source": "synthetic trajectory; no runner executed"
  },
  "legal_terminal_states": [
    "failed"
  ]
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-SA-U01 · safe_abstention

```json
{
  "answerability": null,
  "output": "无法回答。",
  "trace": {
    "product_terminal_state": "failed",
    "error_code": "EVIDENCE_NOT_FOUND",
    "provider_calls": 0,
    "coordinator_calls": 0,
    "artifact_available": true,
    "source": "synthetic trajectory; no runner executed"
  }
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。

## CAL-SA-N01 · safe_abstention

```json
{
  "answerability": "answerable",
  "output": "ready 且 approved is True 时允许 release。",
  "source": {
    "observation_surface": "fixture_final_context",
    "text": "def release_allowed(status, approved):\n    return status == 'ready' and approved is True\n",
    "available": true
  },
  "abstention_attempted": false
}
```

请按适用合同判断 value/verdict 与理由；AI 在回答后提供【正确答案】和标准表述。
