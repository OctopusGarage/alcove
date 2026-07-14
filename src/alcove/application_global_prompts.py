from __future__ import annotations

from pathlib import Path
from typing import Any

from alcove.application_base import _Capability
from alcove.paths import compact_user_path
from alcove.prompt_audit import PromptAuditModule
from alcove.prompt_composer import PromptComposerModule, composed_prompt_dict
from alcove.prompt_curation import PromptCurationModule, candidate_dict
from alcove.prompt_proposals import PromptProposalModule
from alcove.prompt_recommendation import PromptRecommendationModule, recommendation_dict
from alcove.prompts import AddPromptRequest, Prompt, PromptsModule


class _GlobalPromptCapabilities(_Capability):
    """Prompt payload implementation for the global home capability group."""

    def prompt_propose_payload(
        self,
        request: AddPromptRequest,
        *,
        ai_eval_provider: str = "",
    ) -> dict[str, Any]:
        payload = PromptProposalModule(self.runtime.workspace, home=self.runtime.home).propose(
            request,
            ai_eval_provider=ai_eval_provider,
        )
        self._record_action(
            area="prompt",
            action="prompt.propose",
            summary=f"Proposed prompt: {payload['title']}",
            metadata={"id": payload["id"], "action": payload["action"]},
            visible=False,
        )
        return self.runtime.scope_payload(payload)

    def prompt_proposal_payload(self, proposal_id: str) -> dict[str, Any]:
        payload = PromptProposalModule(self.runtime.workspace, home=self.runtime.home).get(
            proposal_id
        )
        return self.runtime.scope_payload(payload)

    def prompt_save_payload(
        self,
        request: AddPromptRequest | None = None,
        *,
        proposal_id: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        if proposal_id:
            request = PromptProposalModule(
                self.runtime.workspace,
                home=self.runtime.home,
            ).request_from_proposal(proposal_id)
        elif not force:
            raise ValueError(
                "Prompt save requires a proposal. Run `alcove prompt propose ... --json`, "
                "then `alcove prompt save --proposal-id <id>`, or pass --force for an "
                "explicit direct write."
            )
        if request is None:
            raise ValueError("Prompt save requires prompt content or --proposal-id.")
        result = PromptsModule(self.runtime.workspace, home=self.runtime.home).save(request)
        audit = PromptAuditModule(
            self.runtime.workspace,
            home=self.runtime.home,
        ).audit(status="active")
        prompt_issues = [
            issue for issue in audit["issues"] if issue["prompt_id"] == result.prompt.id
        ]
        prompt_eval = {
            "verdict": "ready" if not prompt_issues else "needs_review",
            "issues": prompt_issues,
            "audit_status": audit["status"],
            "quality_score": result.prompt.quality.get("score"),
            "proposal_id": proposal_id,
            "force": force,
        }
        self._record_action(
            area="prompt",
            action="prompt.save",
            summary=f"Saved prompt: {result.prompt.title}",
            metadata={"id": result.prompt.id, "proposal_id": proposal_id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {
                    "status": "saved",
                    "path": compact_user_path(result.path),
                    "index_path": compact_user_path(result.index_path),
                    "prompt": _prompt_dict(result.prompt),
                    "prompt_eval": prompt_eval,
                },
                area="prompt",
                action="prompt.save",
                target=result.prompt.id,
                source_of_truth="prompts",
            )
        )

    def prompt_search_payload(
        self,
        query: str = "",
        tag: str = "",
        status: str = "active",
        kind: str = "",
        domain: str = "",
        surface: str = "",
    ) -> dict[str, Any]:
        prompts = [
            _prompt_dict(prompt)
            for prompt in PromptsModule(self.runtime.workspace, home=self.runtime.home).search(
                query=query,
                tag=tag,
                status=status,
                kind=kind,
                domain=domain,
                surface=surface,
            )
        ]
        return self.runtime.scope_payload({"count": len(prompts), "prompts": prompts})

    def prompt_recommend_payload(
        self,
        scenario: str,
        limit: int = 5,
        status: str = "active",
        surface: str = "",
    ) -> dict[str, Any]:
        recommendations = PromptRecommendationModule(
            self.runtime.workspace,
            home=self.runtime.home,
        ).recommend(scenario, limit=limit, status=status, surface=surface)
        return self.runtime.scope_payload(
            {
                "count": len(recommendations),
                "recommendations": [recommendation_dict(item) for item in recommendations],
            }
        )

    def prompt_compose_payload(
        self,
        scenario: str,
        limit: int = 4,
        status: str = "active",
        surface: str = "",
        max_chars_per_prompt: int = 1800,
    ) -> dict[str, Any]:
        composed = PromptComposerModule(
            self.runtime.workspace,
            home=self.runtime.home,
        ).compose(
            scenario,
            limit=limit,
            status=status,
            surface=surface,
            max_chars_per_prompt=max_chars_per_prompt,
        )
        return self.runtime.scope_payload(composed_prompt_dict(composed))

    def prompt_audit_payload(self, status: str = "active") -> dict[str, Any]:
        payload = PromptAuditModule(
            self.runtime.workspace,
            home=self.runtime.home,
        ).audit(status=status)
        return self.runtime.scope_payload(payload)

    def prompt_get_payload(self, prompt_id: str) -> dict[str, Any]:
        prompt = PromptsModule(self.runtime.workspace, home=self.runtime.home).get(prompt_id)
        return self.runtime.scope_payload({"prompt": _prompt_dict(prompt)})

    def prompt_archive_payload(self, prompt_id: str, confirm: bool = False) -> dict[str, Any]:
        payload = PromptsModule(self.runtime.workspace, home=self.runtime.home).archive(
            prompt_id,
            confirm=confirm,
        )
        self._record_action(
            area="prompt",
            action="prompt.archive",
            summary=f"Archived prompt: {prompt_id}",
            metadata={"id": prompt_id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                payload,
                area="prompt",
                action="prompt.archive",
                target=prompt_id,
                source_of_truth="prompts",
                confirmation_required=not confirm,
            )
        )

    def prompt_tags_payload(self) -> dict[str, Any]:
        tags = PromptsModule(self.runtime.workspace, home=self.runtime.home).tags()
        return self.runtime.scope_payload({"count": len(tags), "tags": tags})

    def prompt_rebuild_index_payload(self) -> dict[str, Any]:
        module = PromptsModule(self.runtime.workspace, home=self.runtime.home)
        path = module.rebuild_index()
        return self.runtime.scope_payload(
            {
                "status": "rebuilt",
                "index_path": compact_user_path(path),
                "count": len(module.list(status="")),
            }
        )

    def prompt_candidates_scan_payload(self, source_paths: list[Path]) -> dict[str, Any]:
        payload = PromptCurationModule(self.runtime.workspace, home=self.runtime.home).scan(
            source_paths
        )
        return self.runtime.scope_payload(payload)

    def prompt_candidates_list_payload(self, min_score: float = 0.0) -> dict[str, Any]:
        candidates = PromptCurationModule(
            self.runtime.workspace,
            home=self.runtime.home,
        ).list_candidates(min_score=min_score)
        return self.runtime.scope_payload(
            {
                "count": len(candidates),
                "candidates": [candidate_dict(candidate) for candidate in candidates],
            }
        )

    def prompt_candidates_promote_payload(
        self,
        min_score: float = 0.72,
        limit: int = 0,
    ) -> dict[str, Any]:
        payload = PromptCurationModule(
            self.runtime.workspace,
            home=self.runtime.home,
        ).promote(min_score=min_score, limit=limit)
        self._record_action(
            area="prompt",
            action="prompt.candidates.promote",
            summary=f"Promoted prompt candidates: {payload['count']}",
            metadata={"count": payload["count"]},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                payload,
                area="prompt",
                action="prompt.candidates.promote",
                target="candidates",
                source_of_truth="prompts",
            )
        )


def _prompt_dict(prompt: Prompt) -> dict[str, Any]:
    return {
        "id": prompt.id,
        "title": prompt.title,
        "description": prompt.description,
        "content": prompt.content,
        "kind": prompt.kind,
        "domain": prompt.domain,
        "intent": prompt.intent,
        "surfaces": prompt.surfaces,
        "triggers": prompt.triggers,
        "inputs": prompt.inputs,
        "outputs": prompt.outputs,
        "quality": prompt.quality,
        "tags": prompt.tags,
        "use_cases": prompt.use_cases,
        "source_refs": prompt.source_refs,
        "status": prompt.status,
        "path": f"prompts/{prompt.path.name}",
        "created_at": prompt.created_at,
        "updated_at": prompt.updated_at,
    }
