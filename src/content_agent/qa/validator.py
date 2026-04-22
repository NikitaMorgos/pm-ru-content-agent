from dataclasses import dataclass, field

from content_agent.qa.rules import RULES, Rule
from content_agent.schemas.task_manifest import TaskManifest


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def run_validation(manifest: TaskManifest) -> ValidationResult:
    result = ValidationResult()

    for rule in RULES:
        applies = rule.card_types == "all" or manifest.card_type in rule.card_types
        if not applies:
            continue

        rule_errors = rule.check(manifest)
        if rule_errors:
            if rule.blocking:
                result.errors.extend(rule_errors)
            else:
                result.warnings.extend(rule_errors)

    return result
