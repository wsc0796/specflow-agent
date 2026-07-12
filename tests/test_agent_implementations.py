from specflow.agents.design import DesignAgent
from specflow.agents.models import AgentRole
from specflow.agents.repository_analyst import RepositoryAnalystAgent
from specflow.agents.review import ReviewAgent
from specflow.agents.risk_review import RiskReviewAgent
from specflow.agents.synthesis import SynthesisAgent
from specflow.agents.test_strategy import TestStrategyAgent


class TestAgentIdentities:
    def test_all_agents_have_unique_ids(self):
        agents = [
            RepositoryAnalystAgent(),
            DesignAgent(),
            TestStrategyAgent(),
            RiskReviewAgent(),
            SynthesisAgent(),
            ReviewAgent(),
        ]
        ids = [a.agent_id for a in agents]
        assert len(ids) == len(set(ids))

    def test_all_agents_have_correct_roles(self):
        assert RepositoryAnalystAgent().role == AgentRole.REPOSITORY_ANALYST
        assert DesignAgent().role == AgentRole.DESIGN
        assert TestStrategyAgent().role == AgentRole.TEST_STRATEGY
        assert RiskReviewAgent().role == AgentRole.RISK_REVIEW
        assert SynthesisAgent().role == AgentRole.SYNTHESIS
        assert ReviewAgent().role == AgentRole.REVIEW

    def test_all_agents_satisfy_protocol(self):
        for agent in [
            RepositoryAnalystAgent(),
            DesignAgent(),
            TestStrategyAgent(),
            RiskReviewAgent(),
            SynthesisAgent(),
            ReviewAgent(),
        ]:
            ident = agent.identity
            assert ident.agent_id == agent.agent_id
            assert ident.role == agent.role
            assert ident.version
            result = agent.execute({"test": True})
            assert result["agent_id"] == agent.agent_id
