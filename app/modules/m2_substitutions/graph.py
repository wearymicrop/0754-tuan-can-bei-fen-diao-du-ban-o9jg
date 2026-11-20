from collections import defaultdict


def cyclic_meals(edges):
    forward, reverse = defaultdict(set), defaultdict(set)
    for requested, spare in edges:
        forward[requested].add(spare)
        reverse[spare].add(requested)
    nodes = sorted(forward.keys() | reverse.keys())
    seen, finish = set(), []
    for root in nodes:
        if root in seen:
            continue
        seen.add(root)
        stack = [(root, iter(sorted(forward[root])))]
        while stack:
            node, children = stack[-1]
            child = next(children, None)
            if child is None:
                finish.append(node)
                stack.pop()
            elif child not in seen:
                seen.add(child)
                stack.append((child,iter(sorted(forward[child]))))
    seen.clear()
    output = {}
    for root in reversed(finish):
        if root in seen:
            continue
        seen.add(root)
        stack, component = [root], []
        while stack:
            node = stack.pop()
            component.append(node)
            for parent in reverse[node] - seen:
                seen.add(parent)
                stack.append(parent)
        if len(component) > 1 or root in forward[root]:
            for node in component:
                output[node] = sorted(component)
    return output
