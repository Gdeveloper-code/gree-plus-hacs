# Gree Plus para Home Assistant

[English](README.md) | [Deutsch](README.de.md) | [Español](README.es.md) | [Français](README.fr.md) | [Português (Brasil)](README.pt-BR.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [简体中文](README.zh-Hans.md) | [繁體中文](README.zh-Hant.md)

Gree Plus é uma integração não oficial do Home Assistant, mantida pela comunidade e destinada a entusiastas de tecnologia. Ela conecta aparelhos de ar-condicionado GREE+ compatíveis ao Home Assistant usando a conta GREE+ na nuvem do usuário.

## Recursos

- Controle de energia, modo HVAC, temperatura desejada e velocidade do ventilador.
- Compatibilidade com Celsius, Fahrenheit e intervalos de temperatura dependentes do modelo.
- Atualização de estado após a configuração e os comandos de controle.
- Atualização manual sem consulta contínua em segundo plano.

## Requisitos

- Home Assistant 2026.9.1 ou mais recente.
- Uma conta GREE+ com pelo menos um aparelho de ar-condicionado compatível.
- Acesso do Home Assistant à Internet e ao serviço de nuvem.

## Instalação

1. Abra o HACS no Home Assistant.
2. Adicione este repositório como um repositório personalizado da categoria **Integration**.
3. Baixe o **Gree Plus** e reinicie o Home Assistant.
4. Abra **Configurações > Dispositivos e serviços > Adicionar integração** e selecione **Gree Plus**.

## Configuração

Selecione a região da conta e entre com a conta GREE+ associada aos dispositivos. O Home Assistant armazena os dados da sessão de autenticação para que a integração possa se reconectar.

Se for solicitada uma verificação adicional, abra o link de acesso exibido pelo Home Assistant, conclua a verificação no navegador e cole o endereço completo `http://localhost/...` da barra de endereços. Não envie repetidamente o formulário de credenciais.

## Comportamento de atualização

A integração não faz consultas contínuas. Ela solicita o estado durante a configuração, após comandos de controle e quando uma atualização manual da entidade é solicitada. Alterações feitas fora do Home Assistant podem não aparecer até a próxima atualização.

## Limitações

- Os controles compatíveis se limitam a energia, modo, temperatura desejada e velocidade do ventilador.
- Os modos disponíveis e os intervalos de temperatura dependem dos recursos do dispositivo.
- O funcionamento depende da disponibilidade e da compatibilidade do serviço de nuvem.

## Suporte e privacidade

Relate problemas no rastreador de issues do repositório. Antes de anexar diagnósticos ou registros, remova identificadores da conta, dados de autenticação, identificadores e nomes de dispositivos e informações de localização.

## Isenção de responsabilidade

Este projeto é desenvolvido e mantido exclusivamente como uma integração do Home Assistant. Os mantenedores não oferecem suporte nem endossam seu uso em produtos ou serviços comerciais não relacionados.

Este projeto não é afiliado, endossado nem mantido pela Gree Electric Appliances, Inc. GREE e as marcas relacionadas pertencem aos seus respectivos proprietários. O serviço de nuvem pode mudar ou ficar indisponível sem aviso. Use esta integração por sua conta e risco, revise as automações antes de ativá-las e mantenha acesso a um método oficial de controle. Os mantenedores não se responsabilizam por interrupções do serviço, operação involuntária dos dispositivos, perda de dados ou danos resultantes.

## Licença

MIT
