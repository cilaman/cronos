import type { NodeTypes } from '@xyflow/react';
import { AgentNode } from './AgentNode';
import { TriggerNode } from './TriggerNode';
import { DecisionNode } from './DecisionNode';
import { WaitNode } from './WaitNode';
import { AggregatorNode } from './AggregatorNode';

export const nodeTypes: NodeTypes = {
  agent: AgentNode,
  trigger: TriggerNode,
  decision: DecisionNode,
  wait: WaitNode,
  aggregator: AggregatorNode,
};
