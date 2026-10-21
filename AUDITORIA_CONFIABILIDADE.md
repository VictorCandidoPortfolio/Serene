# Auditoria de confiabilidade do motor

Regra adotada: **só se apresenta o que tem dado e critério definido.** Sem dado suficiente, não há
resultado nem justificativa; cada limitação aparece uma vez, e só quando ajuda a aluna a prosseguir.

## O que foi encontrado, corrigido e removido

| # | Onde (origem) | Problema | Correção |
|---|---|---|---|
| 1 | `engine/compatibility.py` | Par sem relação cadastrada recebia nota 0,5 ("neutra") e entrava na média: aparecia ~50 % sem cálculo válido. | Par sem relação **não é avaliado** e fica fora da média. Sem nenhum par avaliável, `score = null`. |
| 2 | `engine/compatibility.py` | Uma frase por par não avaliado, repetida na lista de pares e nos alertas. | Pares não avaliados saem da lista; **uma linha por causa** nos alertas ("Sem família reconhecida: …", "Sem relação cadastrada entre …"). |
| 3 | `engine/compatibility.py` + `services/motor.py` | Nota calculada com relações de exemplo era mostrada como medida. | Resposta traz `pares_avaliados`, `pares_total` e `base_exemplo`; a interface avisa que são relações de exemplo. |
| 4 | `engine/vectors.py` | Eixo calculado com 10 % do peso do acorde aparecia como se o descrevesse inteiro; um aviso por eixo. | `peso_score/validacao.cobertura_minima_eixo` (0,5): abaixo disso o eixo e a pirâmide ficam sem valor. **Um** aviso lista tudo o que falta. |
| 5 | `services/criacoes_service.py` (identidade) | "Nenhum território próximo" + "eixos sem dado" repetiam a mesma ausência. | Uma orientação, só se faltam características; território não próximo não gera mensagem. |
| 6 | Front: identidade/coleções | Porcentagem de território vinha de distância sobre vetores de exemplo (não é medida válida). | Removida (texto, barra e selo). Fica o nome e o que combina. |
| 7 | Front: `Eixos` | Linha "sem dado" e barra vazia para cada eixo. | Só eixos com valor; sem nenhum, nada é desenhado. |
| 8 | Motor de criação | Pedido sem emoção/preferência gerava "identidade" a partir do ponto neutro de partida. | Status `pedido_incompleto`: sem identidade nem acorde. |
| 9 | Motor de criação | Essência sem características entrava com nota neutra e podia ser escolhida. | Fica de fora e é citada **uma vez**; sem nenhuma essência com dados: `dados_insuficientes`. |
| 10 | Motor de criação | "Traz delicadeza floral" era frase fixa por família, igual para toda essência. | Removida. A explicação cita só fatos: território cadastrado, eixos realmente próximos do pedido, papel informado >50 %. Sem fato, vem vazia. |
| 11 | Motor de criação | "A combinação tende a favorecer essa direção" mesmo com o acorde longe do pedido. | Só diz em quais eixos o acorde calculado fica próximo; nada mais. |
| 12 | Motor de criação | Selo "confiança alta/média/baixa" com limiares inventados. | Substituído por `dados_suficientes` (fato), motivos nos avisos/lacunas. |
| 13 | Motor de criação | "Fraco" afirmado quando o score baixo vinha de falta de dado. | `fraco` só vale com dado; senão vale o aviso de características faltando. |
| 14 | Motor de criação | Pirâmide calculada com papel de só parte das essências. | Mesma cobertura mínima do item 4. |
| 15 | Motor de criação | Avisos e lacunas repetidos (fraco + lacuna + pouca variedade). | Cada causa uma vez; lacunas iguais não se repetem. |

## Não corrigido (limitação conhecida)

- Compatibilidade já **gravada** em versões antigas de acorde continua como foi calculada; só versões novas usam a regra nova.
- Todas as regras do seed (relações, vetores de território, pesos) ainda são **conteúdo de exemplo**; a interface agora diz isso na compatibilidade.

## Segunda rodada (especificação do motor de perfumaria)

| # | Problema | Correção |
|---|---|---|
| 16 | Compatibilidade dava ~80 % só por duas essências serem da mesma família. | Mesma família **não é avaliada**: sem relação cadastrada entre matérias-primas não há critério. |
| 17 | O aviso "tende a ficar isolada" vinha de heurística não calibrada. | Removido da tela; a heurística fica só na seleção interna. |
| 18 | Concentração livre/faixas (2–8 %, 5–15 %...). | Só as da especificação: body splash 7/10/15, perfume 20/25/30 (dados em `peso_score/formulacao_*`). |
| 19 | Base = uma linha ("resto é álcool"). | Base com composição definida por produto (componentes e % da base, somando 100). **Valores de exemplo a confirmar.** |
| 20 | Fórmula não fazia parte da versão do acorde. | `acordes.formulacao` (migration 0011): editar cria nova versão; versão sem pedido herda a anterior. |
| 21 | Cadastro sem ficha técnica. | `essencias.ficha`: identificação, notas, documentação, limites de uso (com fonte) e restrições. Documentado ≠ avaliação sensorial ≠ desconhecido. |
| 22 | Limites e adequação à categoria não eram verificados. | Limite documentado fixa a essência e redistribui o excedente (ou recusa); restrição documentada bloqueia; sem limite, **um** aviso. |
| 23 | Sem entrada em linguagem natural. | `engine/linguagem.py`: só palavras cadastradas (`sinonimos`), com negação; mostra o que entendeu. Sem IA. |

## Calculadora de formulação

`engine/formulacao.py` (Decimal): concentrado = volume × concentração ÷ 100. Essências dividem o concentrado por
pesos relativos (ou manualmente), respeitando limites documentados; a soma é exatamente 100 %; a base segue a
composição do produto; massa só com densidade informada. A fórmula sai sempre como **não validada**.
Pendente de dados/validação técnica: composição real da base, limites IFRA/fornecedor por essência, densidades.
