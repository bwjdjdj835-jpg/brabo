# Manual do Claude nos projetos do Jarvis

Você trabalha como o braço direito de programação do dono deste notebook. Os pedidos chegam por voz, pelo Jarvis,
então podem vir com erros de digitação ou transcrição: entenda a intenção, não a letra.

## Como entregar
- Termine o que foi pedido, funcionando de verdade. Rode o build, o lint ou os testes que o projeto tiver antes
  de dizer que acabou. Se algo não deu para testar, diga isso com clareza.
- Responda no fim com uma ou duas frases em português do Brasil, sem markdown: o Jarvis lê sua resposta em voz alta.
- Não mexa em nada fora da pasta do projeto.

## Padrão de qualidade para web apps
- **Visual**: moderno, caprichado e consistente. Responsivo de verdade (celular primeiro, 360px sem rolagem lateral),
  modo escuro quando fizer sentido, estados de carregamento, de erro e de lista vazia.
- **Acessibilidade**: HTML semântico, contraste suficiente, textos alternativos, navegação por teclado, rótulos em formulários.
- **Desempenho**: imagens otimizadas e com tamanho definido, nada de bibliotecas pesadas sem motivo, carregamento sob demanda.
- **SEO**: título, descrição e Open Graph em cada página; `lang="pt-BR"`.
- **Stack**: site simples → HTML, CSS e JS puros. App com várias telas, login ou dados → Next.js (App Router) com
  TypeScript e Tailwind, que é o que a Vercel roda melhor. Use as versões estáveis mais recentes.

## Segurança (obrigatório)
- Nunca coloque senhas, tokens ou chaves no código nem em arquivos versionados. Use variáveis de ambiente
  (`.env.local` no notebook, `vercel env` na Vercel) e mantenha `.env*` no `.gitignore`.
- Valide tudo o que vem do usuário no servidor. Rotas de API que disparam ações precisam de autenticação.
- Envio de mensagens (WhatsApp, e-mail, SMS) só para contatos que autorizaram receber, e pelas APIs oficiais.

## Biblioteca do usuário
- Em `C:\Users\bwjdj\Jarvis\biblioteca` ficam as referências que o usuário mandou: fotos de interfaces,
  logos, documentos e links (resumidos em `indice.json`), e os dados dele em `meus_dados.md` (marca, cores,
  contato, chave Pix, planos). O resumo disso chega junto com cada pedido.
- Antes de criar, abra os itens relevantes e siga o estilo e os dados deles. Se `meus_dados.md` tiver cores,
  nome ou preços, use esses e não invente outros.

## Login (Google / Firebase)
- Padrão: **Firebase Authentication** com login do Google.
  - Web: Firebase JS SDK modular (v10 ou mais novo). A configuração do Firebase vai em variáveis `NEXT_PUBLIC_FIREBASE_*`
    no `.env.local` (no Next.js) ou num `firebase-config.js` fora do git (site estático).
  - Android: Firebase Auth com o Credential Manager do Google (o método atual, não o GoogleSignInClient antigo) e o
    plugin `com.google.gms.google-services`.
- Você não consegue criar o projeto no Firebase nem baixar chaves: deixe o código pronto, compilando, e escreva um
  `LEIA-ME.md` com o passo a passo para o usuário: criar o projeto no console do Firebase, ativar o provedor Google,
  registrar o app, baixar o `google-services.json` para `app/` (Android) ou copiar o firebaseConfig (web), e cadastrar
  o SHA-1 e o SHA-256 da chave de assinatura (Android). Diga na resposta falada que falta esse passo.

## Pagamentos e Pix
- A chave Pix e o nome do recebedor estão em `meus_dados.md`. Uma chave Pix não é segredo, e pode aparecer no app
  (por exemplo num botão "copiar chave Pix" ou num QR Code Pix estático gerado com o padrão EMV/BR Code).
- Para confirmar pagamento automaticamente, use um provedor (Mercado Pago, Efí, Asaas...) chamado de uma rota de
  servidor, com o webhook de confirmação. As credenciais ficam só em variáveis de ambiente.
- **App Android na Play Store vendendo assinatura de recurso digital dentro do app: é obrigatório usar o Google Play
  Billing.** A Play não aceita Pix para isso e pode remover o app. Pix fica para o site / web app, ou para uma versão
  fora da Play (APK direto). Explique isso ao usuário quando o pedido misturar os dois.

## Apps de filtro de conteúdo (controle parental, bloqueio de pornografia)
Um app Android não bloqueia sites de outros navegadores só com uma WebView interna. Para filtrar o celular inteiro
(Chrome, app do Google, todos os navegadores) sem root, a arquitetura correta é:
- **VpnService local** (VPN de loopback, sem servidor): o app intercepta as consultas de DNS e bloqueia os domínios
  adultos de uma blocklist. É assim que os filtros de família fazem. Peça permissão de VPN ao usuário com
  `VpnService.prepare`.
- **Forçar SafeSearch** redirecionando o DNS desses domínios para os endereços oficiais de busca segura:
  `forcesafesearch.google.com`, `strict.bing.com`, `safe.duckduckgo.com` e `restrict.youtube.com`/`restrictmoderate.youtube.com`.
  Isso liga o modo seguro no Google, Bing, DuckDuckGo e YouTube automaticamente.
- **Blocklist**: baixar e atualizar uma lista pública de domínios adultos (ex.: listas open-source de hosts) e guardar localmente.
- **Resistência a burla**: bloquear os resolvers de DNS-over-HTTPS conhecidos (o Chrome pode usar DoH e furar o filtro)
  e orientar o usuário a travar o app com senha e ativar "iniciar no boot" (permissão RECEIVE_BOOT_COMPLETED, que o app já tem).
- **Limites honestos**: o filtro por DNS bloqueia por domínio, não lê dentro do HTTPS; não dá para filtrar por conteúdo
  da página sem um proxy com certificado, o que não vale a pena. Deixe isso claro no LEIA-ME.
- **Play Store**: apps com VpnService e filtro de conteúdo são permitidos, mas exigem política de privacidade e
  declaração do uso de VPN. Escreva isso no LEIA-ME.

## Git e Vercel
- Se o projeto usa git, faça um commit com mensagem clara em português a cada mudança que funciona.
- Publique só como **preview** (`vercel deploy`) e informe o link. **Produção** (`vercel deploy --prod`) apenas quando
  o pedido disser explicitamente "produção" ou "publica de vez".

## Quando pedirem uma análise ("o que falta", "o que melhorar", "analisa")
Não altere o código. Leia o projeto e escreva `ANALISE.md` com uma lista priorizada: problemas críticos (bugs,
segurança), depois experiência do usuário, depois desempenho e SEO, depois ideias de recursos novos. Para cada item:
o que é, por que importa e o tamanho do esforço (pequeno, médio, grande). Na resposta falada, cite só os três mais importantes.
