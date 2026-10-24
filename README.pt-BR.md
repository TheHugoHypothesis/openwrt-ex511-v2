# TP-Link EX511 V2 — OpenWrt com NSS

[English](README.md) · [Índice técnico](docs/ex511-v2/README.md) ·
[Instalação por SSH em português](docs/ex511-v2/installation-ssh.pt-BR.md)

Este repositório reúne o código e a instalação experimental do OpenWrt no
**EX511 V2 por root SSH, sem precisar enviar comandos pela UART**.
O aparelho testado já inicia OpenWrt persistentemente pelo NAND, com Ethernet,
Wi-Fi nas duas bandas, NSS, PPPoE e IPv6 em funcionamento.

**Não é uma versão oficial estável do OpenWrt nem um instalador universal.**
O acesso root ao firmware original precisa existir antes: o projeto não
publica senha compartilhada, exploração da interface web ou desbloqueio
universal. Um login chamado admin não basta; é necessário comprovar UID 0.

O firmware testado usa Linux **6.18.55** e OpenWrt **SNAPSHOT
r0+37938-ff5b0529bb8**. A branch padrão `ex511-v2` contém o código e a
organização atual; commits posteriores de documentação não representam uma
nova imagem de firmware testada.

## Leia nesta ordem

1. [Hardware e o que sabemos da UART](docs/ex511-v2/hardware.md).
2. [Recuperação e seus limites](docs/ex511-v2/recovery.md).
3. [Instalação por SSH — passo a passo](docs/ex511-v2/installation-ssh.pt-BR.md).
4. [Compilação e dados privados necessários](docs/ex511-v2/build-current.md).
5. [Resultados e limitações dos testes](docs/ex511-v2/results.md).
6. [Rede atual, IPv6 e desempenho](docs/ex511-v2/network-operation.md).

A publicação de documentação não inclui firmware privado. Os [builds públicos
de teste por CI](docs/ex511-v2/public-builds.md), quando disponíveis, excluem
o BDF regional/FEM privado; o 5 GHz exige provisionamento local compatível. Use os dados
do seu aparelho, mantenha backups privados e não use firmware do AX55.

## UART e recuperação

Recebemos os logs pela UART, mas não conseguimos entrada confiável.
**Não confirmamos fisicamente uma interrupção na trilha RX do EX511.**
A hipótese surgiu pela semelhança com o AX55, cuja documentação descreve
uma interrupção de fábrica. Não há localização de ponte de solda validada
para o EX511 neste projeto.

A gravação e seleção do sistema foram feitas por SSH; a UART serviu somente
para observar. Isso não equivale a um teste separado com o aparelho sempre
fechado e sem monitoramento. O stock foi preservado na outra partição, mas
não existe retorno automático garantido se o kernel iniciar e depois travar.
A entrada na recuperação web foi testada; a restauração por upload não foi.

## Contribuições e crédito

O port original de fl1ck3r, as contribuições EX511 de gusfm e a base NSS de
kuncy7 são fundamentais. Este trabalho acrescenta leitura/validação de dados
de fábrica, perfis protegidos na partição secundária, controle de boot por
SSH e resultados de instalação/testes. Não reivindicamos a criação de toda
a pilha Ethernet, NSS ou Wi-Fi. Veja [créditos](docs/ex511-v2/credits.md).
