"""Harder algorithmic repair families with independent small-instance oracles."""
import ast
from fractions import Fraction


def allocation_ref(workers,jobs,quotes):
    cost={(w,j):c for w,j,c in quotes}
    slots=[j for j,d in jobs for _ in range(d)]
    remaining=dict(workers)
    best=(0,0)
    def search(i,filled,total):
        nonlocal best
        if i==len(slots):
            if filled>best[0] or (filled==best[0] and total<best[1]):
                best=(filled,total)
            return
        search(i+1,filled,total)
        j=slots[i]
        for w in remaining:
            if remaining[w]>0 and (w,j) in cost:
                remaining[w]-=1
                search(i+1,filled+1,total+cost[w,j])
                remaining[w]+=1
    search(0,0,0)
    return {'filled':best[0],'cost':best[1]}


def expression_ref(text):
    # AST visitor is independent of the candidate's tokenizer/Pratt parser.
    tree=ast.parse(text.strip().replace('^','**'),mode='eval')
    def evaluate(n):
        if isinstance(n,ast.Constant) and type(n.value) is int:
            return Fraction(n.value)
        if isinstance(n,ast.UnaryOp):
            v=evaluate(n.operand)
            return -v if isinstance(n.op,ast.USub) else v
        a,b=evaluate(n.left),evaluate(n.right)
        if isinstance(n.op,ast.Add): return a+b
        if isinstance(n.op,ast.Sub): return a-b
        if isinstance(n.op,ast.Mult): return a*b
        if isinstance(n.op,ast.Div): return a/b
        if isinstance(n.op,ast.Pow): return a**b
        raise ValueError('operator')
    return str(evaluate(tree.body))


HARD_SPECS={
'allocation': (
    'solve(workers,jobs,quotes): workers=[[name,capacity],...], jobs=[[name,demand],...], quotes=[[worker,job,cost_per_unit],...] (unique pairs, nonnegative integer costs). Unquoted assignments are forbidden. Allocate integer units, never exceed a worker capacity or job demand. First maximize total filled demand, then minimize cost among all such allocations. Return exactly {filled:int,cost:int}. A greedy edge ordering is insufficient; reassignment may be necessary. Names in each list are unique. Empty and disconnected instances are valid; do not mutate inputs.',
    {
        'network.py': "def edge(graph,a,b,cap,cost):\n    graph[a].append([b,len(graph[b]),cap,cost])\n    graph[b].append([a,len(graph[a])-1,0,-cost])\n",
        'paths.py': "def shortest(graph,source):\n    n=len(graph)\n    distance=[None]*n\n    parent=[None]*n\n    distance[source]=0\n    for turn in range(n-1):\n        changed=False\n        for a in range(n):\n            if distance[a] is not None:\n                for idx,e in enumerate(graph[a]):\n                    b,rev,cap,cost=e\n                    if cap>0 and (distance[b] is None or distance[a]+cost<distance[b]):\n                        distance[b]=distance[a]+cost\n                        parent[b]=(a,idx)\n                        changed=True\n        if not changed:\n            break\n    return distance,parent\n",
        'augment.py': "def send(graph,parent,source,sink):\n    path=[]\n    v=sink\n    while v!=source:\n        a,idx=parent[v]\n        path.append((a,idx))\n        v=a\n    amount=min(graph[a][idx][2] for a,idx in path)\n    for a,idx in path:\n        b,rev,cap,cost=graph[a][idx]\n        graph[a][idx][2]-=amount\n        graph[b][rev][2]+=amount\n    return amount\n",
        'main.py': "from network import edge\nfrom paths import shortest\nfrom augment import send\ndef solve(workers,jobs,quotes):\n    wmap={name:i+1 for i,(name,c) in enumerate(workers)}\n    jmap={name:len(workers)+i+1 for i,(name,d) in enumerate(jobs)}\n    source,sink=0,len(workers)+len(jobs)+1\n    graph=[[] for i in range(sink+1)]\n    for name,c in workers:\n        edge(graph,source,wmap[name],c,0)\n    for name,d in jobs:\n        edge(graph,jmap[name],sink,d,0)\n    for w,j,c in quotes:\n        edge(graph,wmap[w],jmap[j],sum(d for name,d in jobs),c)\n    filled,total=0,0\n    while True:\n        distance,parent=shortest(graph,source)\n        if distance[sink] is None:\n            break\n        amount=send(graph,parent,source,sink)\n        filled+=amount\n        total+=amount*distance[sink]\n    return {'filled':filled,'cost':total}\n",
    }, [('network.py','len(graph[a])-1,0,-cost','len(graph[a])-1,0,cost'),
        ('paths.py','range(n-1)','range(1)'),
        ('augment.py','amount=min(','amount=max(')]),
'expression': (
    'solve(text): text is a valid arithmetic expression of nonnegative integer literals, whitespace, parentheses, unary +/- and binary + - * / ^. Use exact rational arithmetic. Power is right-associative and binds MORE tightly than unary signs; multiplication/division are left-associative and bind more tightly than addition/subtraction. Exponents evaluate to nonnegative integers; no zero divisor occurs. Return the canonical fractions.Fraction string, integer if denominator=1, else numerator/denominator. Example -2^2 is -4, 2^3^2 is 512, 8/4/2 is 1. Input unchanged.',
    {
        'lex.py': "def tokens(text):\n    out=[]\n    i=0\n    while i<len(text):\n        c=text[i]\n        if c.isspace():\n            i+=1\n        elif c.isdigit():\n            j=i+1\n            while j<len(text) and text[j].isdigit():\n                j+=1\n            out.append(text[i:j])\n            i=j\n        else:\n            out.append(c)\n            i+=1\n    return out\n",
        'binding.py': "def powers(op):\n    if op in ('+','-'): return (10,11)\n    if op in ('*','/'): return (20,21)\n    if op=='^': return (40,40)\n    return (-1,-1)\n",
        'unary.py': "def precedence():\n    return 30\n",
        'main.py': "from fractions import Fraction\nfrom lex import tokens\nfrom binding import powers\nfrom unary import precedence\ndef parse(ts,pos,minimum):\n    token=ts[pos]\n    if token in ('+','-'):\n        value,pos=parse(ts,pos+1,precedence())\n        if token=='-': value=-value\n    elif token=='(':\n        value,pos=parse(ts,pos+1,0)\n        if ts[pos]!=')': raise ValueError('parenthesis')\n        pos+=1\n    else:\n        value=Fraction(int(token))\n        pos+=1\n    while pos<len(ts):\n        op=ts[pos]\n        left,right=powers(op)\n        if left<minimum: break\n        other,pos=parse(ts,pos+1,right)\n        if op=='+': value+=other\n        elif op=='-': value-=other\n        elif op=='*': value*=other\n        elif op=='/': value/=other\n        elif op=='^': value=value**other\n    return value,pos\ndef solve(text):\n    ts=tokens(text)\n    value,pos=parse(ts,0,0)\n    if pos!=len(ts): raise ValueError('trailing tokens')\n    return str(value)\n",
    }, [('lex.py','while j<len(text) and text[j].isdigit():','while False:'),
        ('binding.py',"if op=='^': return (40,40)","if op=='^': return (40,41)"),
        ('unary.py','return 30','return 50')]),
}


def hard_cases(family,rng):
    out=[]
    def add(group,*args):
        out.append({'group':group,'args':list(args)})
    if family=='allocation':
        add('empty',[],[],[])
        add('reroute',[['a',1],['b',1]],[['x',1],['y',1]],[['a','x',1],['a','y',2],['b','x',2],['b','y',100]])
        add('bottleneck',[['a',4]],[['x',1]],[['a','x',3]])
        add('shortfall',[['a',2]],[['x',1],['y',3]],[['a','x',2]])
        add('reverse_order',[['b',1],['a',1]],[['y',1],['x',1]],[['a','x',1],['a','y',2],['b','x',2],['b','y',100]])
        for i in range(30):
            workers=[[f'w{j}',rng.randint(1,3)] for j in range(rng.randint(2,3))]
            jobs=[[f'j{j}',rng.randint(1,2)] for j in range(rng.randint(2,3))]
            quotes=[[w,j,rng.randint(0,20)] for w,c in workers for j,d in jobs if rng.random()<.8]
            rng.shuffle(workers); rng.shuffle(jobs); rng.shuffle(quotes)
            add('random',workers,jobs,quotes)
    else:
        add('literal',str(rng.randint(10,99)))
        add('unary',f'-{rng.randint(2,5)}^2')
        add('power','2^3^2')
        add('rational','8/4/2 + 1/3')
        add('parentheses','-(12 + 3) * (5 - 8)')
        def expression(depth):
            if depth==0: return str(rng.randint(1,20))
            op=rng.choice(['+','-','*','/','^'])
            a=expression(depth-1)
            b=str(rng.randint(1,5)) if op=='/' else str(rng.randint(0,3)) if op=='^' else expression(depth-1)
            value=f'({a} {op} {b})'
            return '-'+value if rng.random()<.25 else value
        for i in range(30): add('random',expression(rng.randint(1,3)))
    return out
