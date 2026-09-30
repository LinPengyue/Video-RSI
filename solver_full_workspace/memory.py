class Memory:
    """Store structured observations and action history."""
    def __init__(self):
        self.items = []

    def add(self, decision, observation):
        self.items.append({"tool": decision["tool"], "arguments": decision.get("arguments", {}), "observation": observation})
