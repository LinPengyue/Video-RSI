/** Headless session creation and resume. */
import fs from 'node:fs/promises'
import type { Context } from '@deepseek-ai/cordis'
import z from '@deepseek-ai/schemastery'
import { installModelSelection } from '@deepseek-ai/dsh-agent'
import type { ModelSelectionRef } from '@deepseek-ai/dsh-agent'
import { createUserMessage } from '@deepseek-ai/dsh-llm'
import { SessionId } from '@deepseek-ai/dsh-session'
import type {} from '@deepseek-ai/dsh-agent-default-model'
import type {} from '@deepseek-ai/cordis-plugin-loader'
import type {} from '@deepseek-ai/dsh-cmdline'

export const name = 'full-candidate-session-runner'
export const inject = ['agentDefaultModel', 'agents', 'sessions']
export interface Config { task: string }
export const Config: z<Config> = z.object({ task: z.string().required() })

export function apply(ctx: Context, config: Config): void {
  const exit = ctx.get('appExit')
  if (exit === undefined) throw new Error('appExit missing')
  async function run(): Promise<void> {
    await ctx.get('loader')?.await()
    const agents = ctx.get('agents')!
    const sessions = ctx.get('sessions')!
    const selection = ctx.get('agentDefaultModel')!.currentSelection()
    const id = process.env.FULL_CANDIDATE_SESSION_ID
    const receipt = process.env.FULL_CANDIDATE_SESSION_RECEIPT
    if (!id || !receipt) throw new Error('session identity / receipt missing')
    const options = {
      agentOptions: { provider: selection.provider, model: selection.model },
      setup: (agentCtx: Context) => {
        const selected: ModelSelectionRef = { current: selection, assembled: undefined }
        installModelSelection(agentCtx, selected)
      },
    }
    const resumed = process.env.FULL_CANDIDATE_RESUME === '1'
    const { agent } = resumed
      ? await agents.resume({ ...options, resumeSessionId: SessionId(id) })
      : await agents.create({ ...options, sessionId: SessionId(id), meta: { cwd: process.cwd() } })
    await agent.whenIdle()
    const firstSeq = agent.session.seq
    agent.followup(createUserMessage({ content: [{ type: 'text', text: process.env.FULL_CANDIDATE_TASK ?? config.task }], source: { kind: 'user' } }))
    await agent.whenIdle()
    await sessions.flush(agent.session)
    const events = agent.session.events.filter(event => event.seq >= firstSeq)
    const end = events.filter(event => event.type === 'turn/end').at(-1)
    const reason = end?.type === 'turn/end' ? end.data.reason : undefined
    await fs.writeFile(receipt, JSON.stringify({ session_id: id, resumed, first_seq: firstSeq, final_seq: agent.session.seq, reason }))
    for (const event of events) {
      if (event.type === 'assistant/message') {
        process.stdout.write(event.data.message.content.filter(block => block.type === 'text').map(block => block.text).join('') + '\n')
      }
    }
    exit!(reason?.kind === 'completed' ? 0 : 1)
  }
  void run().catch(error => { process.stderr.write(String(error) + '\n'); exit!(1) })
}
