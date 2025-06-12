# 🌊 INSTABIDS HOMEOWNER AGENT SWARM - COMPLETE CODEX BUILD PLAN

## 🎯 PROJECT OVERVIEW
Building the world's first living AI organism - starting with the Homeowner Agent Swarm as proof of concept. This demonstrates the complete event-driven, self-organizing architecture that will scale to the full 50+ agent system.

**What We're Building:**
- 5 Core Homeowner Agents working in parallel swarms
- Event-driven coordination via Redis Streams
- 3-tier memory system using Redis + Supabase
- Contact protection system (business model core)
- Dynamic agent-aware UI using CopilotKit
- Complete vertical slice proving the full architecture

## 🤖 QUICK START FOR AI AGENTS

### Your Agent Assignment:
- **Agent 1-6:** Check `AGENT_ASSIGNMENTS.md` for your specific domain
- **Build Order:** Agent 1 → Agent 2-4 (parallel) → Agent 5-6
- **Tools:** Use MCP tools as specified in `MCP_TOOLS_REFERENCE.md`

### Critical Rules:
- ❌ **NO direct agent communication** (use Redis Streams only)
- 🛡️ **Contact protection is ABSOLUTE** (business model core)
- 💰 **Cost limits:** $0.05/event, $1000/day
- 📝 **Update** `build_coordination/build_status.json` after each phase
- 🔧 **ALL tool calls via MCP** (no direct API calls)

### Essential Files to Read:
1. `CODEBASE_MANIFEST.json` - Complete project context
2. `AGENT_ASSIGNMENTS.md` - Your specific build instructions
3. `MCP_TOOLS_REFERENCE.md` - Tool usage patterns
4. `build_coordination/build_status.json` - Current progress

## 📁 PROJECT STRUCTURE
```
instabids-homeowner-swarm/
├── CODEBASE_MANIFEST.json          # Complete project metadata
├── BOILERPLATE_BUILD_PROGRESS.md   # Repository build tracking
├── README.md                       # This file (Master coordination)
├── AGENT_ASSIGNMENTS.md            # Detailed agent build paths
├── MCP_TOOLS_REFERENCE.md          # MCP tool usage patterns
├── ARCHITECTURE_GUIDE.md           # System design principles
├── 
├── build_coordination/             # Build process management
│   ├── build_status.json          # Real-time build tracking
│   ├── agent_dependencies.json    # Build order dependencies
│   ├── integration_checkpoints.json # Validation milestones
│   └── mcp_tool_usage.json        # Tool allocation per agent
├── 
├── core/                           # Agent 1 Domain - Foundation
│   ├── events/                    # Redis Streams infrastructure
│   ├── memory/                    # 3-tier memory system
│   ├── security/                  # Contact protection core
│   └── base/                      # Shared agent patterns
├── 
├── agents/                         # Agent 2-6 Domains - Business Logic
│   ├── homeowner_intake/          # Agent 2 - NLP Processing
│   ├── project_scope/             # Agent 3 - Data Structuring
│   ├── communication_filter/      # Agent 4 - Security Protection
│   ├── payment_gate/              # Agent 5 - Payment Processing
│   └── ui_generator/              # Agent 6 - Dynamic Interface
├── 
├── ui/                            # Frontend application
│   ├── src/components/            # React components
│   ├── src/hooks/                 # Agent-aware hooks
│   └── src/pages/                 # Application pages
├── 
├── tests/                         # Comprehensive testing
│   ├── integration/               # Cross-agent testing
│   ├── e2e/                      # Full workflow testing
│   ├── agent_specific/           # Individual agent tests
│   ├── performance/              # Scale and load testing
│   └── security/                 # Security validation
├── 
├── deployment/                    # Infrastructure setup
│   ├── docker-compose.yml        # Local development stack
│   ├── redis.conf                # Redis configuration
│   └── scripts/                  # Deployment automation
└── 
└── docs/                         # Documentation
    ├── API_REFERENCE.md
    ├── EVENT_SCHEMAS.md
    ├── SECURITY_GUIDE.md
    └── DEPLOYMENT_GUIDE.md
```

## 🏗️ ARCHITECTURE FOUNDATION

### 3-Tier Memory System:
- **Tier 1:** Redis (42 MCP tools) - Real-time events, agent coordination, temporary state
- **Tier 2:** Supabase (28 MCP tools) - Event store (audit trail) + Read models (fast queries)
- **Tier 3:** Dynamic UI - CopilotKit morphing based on agent activity

### Event-Driven Core:
- **NO direct agent communication** - only Redis Stream events
- **Complete audit trail** - every action stored forever
- **Self-organizing** - agents spawn based on queue depth
- **Self-healing** - automatic recovery from failures

### MCP Tools Mapping:
| Agent | Primary Tools | Purpose |
|-------|---------------|---------|
| Agent 1 | digitalocean, redis, supabase, docker | Infrastructure foundation |
| Agent 2 | context7, redis, supabase, docker | Homeowner intake processing |
| Agent 3 | context7, redis, supabase | Project scope structuring |
| Agent 4 | context7, redis, supabase | Communication filtering |
| Agent 5 | context7, redis, supabase | Payment processing |
| Agent 6 | context7, github, redis, supabase | Dynamic UI generation |

## 🧪 TESTING STRATEGY

- **Framework:** pytest + asyncio for Python, Jest for TypeScript
- **Location:** `tests/agent_specific/test_{agent_name}.py`
- **Run Tests:** `python -m pytest tests/`
- **Coverage Required:** >80% for all agent domains
- **Security Tests:** Contact protection must have 100% block rate
- **Performance:** 1000+ events/minute processing

## 🚀 QUICK DEPLOYMENT

### Prerequisites:
- **Redis:** Use MCP redis tools (connection configured)
- **Supabase:** Use MCP supabase tools (API token configured)
- **MCP Tools:** Pre-configured (see CODEBASE_MANIFEST.json)

### Start Building:
1. Check `BOILERPLATE_BUILD_PROGRESS.md` for current repository status
2. Check `build_coordination/build_status.json` for agent progress
3. Follow your agent assignment in `AGENT_ASSIGNMENTS.md`
4. Use MCP tools as documented in `MCP_TOOLS_REFERENCE.md`
5. Test continuously with `python -m pytest tests/agent_specific/`

### Critical Integration Points:
- **Event Streams:** All communication via Redis Streams
- **Contact Protection:** Multi-layer detection in every message
- **Payment Gates:** Contact info ONLY released after payment
- **UI Morphing:** Real-time adaptation to agent activity

## 🛡️ SECURITY MODEL

### Contact Protection (Business Model Core):
- **Detection:** Regex + NLP + Intent + Obfuscation + Context analysis
- **Escalation:** Warning → Restriction → Suspension → Ban
- **Enforcement:** Real-time filtering of ALL communication
- **Audit:** Complete violation logging and compliance

### Cost Controls:
- **Daily Limit:** $1000 total
- **Per-Event Limit:** $0.05 maximum
- **Circuit Breaker:** Automatic shutdown on limit breach

## 🔄 BUILD COORDINATION

### Agent Dependencies:
1. **Agent 1** (Infrastructure) → Builds foundation for all others
2. **Agents 2-4** (Parallel) → Core business logic (depends on Agent 1)
3. **Agents 5-6** (Final) → Payment and UI (depends on 1-4)

### Progress Tracking:
- **Repository Status:** `BOILERPLATE_BUILD_PROGRESS.md`
- **Agent Progress:** `build_coordination/build_status.json`
- **Handoff Protocol:** Event completion triggers next agent

## 📊 SUCCESS METRICS

### Technical:
- **Event Throughput:** 1000+ events/minute
- **Response Time:** <100ms for filtering
- **Uptime:** 99.9% availability
- **Test Coverage:** >80% all domains

### Business:
- **Contact Protection:** 100% violation detection
- **Revenue Protection:** Zero unauthorized contact sharing
- **Cost Control:** Within budget limits
- **User Experience:** Seamless agent coordination

---

**🎯 Ready to build the world's first living AI organism.**

**Repository:** https://github.com/Instabidsai/instabids-homeowner-swarm  
**Status:** Building foundation boilerplate  
**Next:** Create complete agent domains and starter code
