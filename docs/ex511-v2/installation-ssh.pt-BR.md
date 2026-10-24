# Instalação do EX511 V2 por root SSH — passo a passo

Os símbolos $EX511_HOST, $OPENWRT_HOST, $PC_SOURCE, $RECOVERY_HOST e
$RECOVERY_PC substituem endereços particulares: defina-os conforme o seu
aparelho e a sua rede isolada antes de copiar comandos. As versões antigas
são referências históricas; veja [source-provenance.md](source-provenance.md).

[Guia técnico completo em inglês](installation-ssh.md) · [Compilação](build-current.md) · [Recuperação](recovery.md)

Este é o roteiro reorganizado da instalação feita em **um EX511 V2**. Não é
um instalador universal nem uma promessa de compatibilidade com qualquer
firmware de operadora. Não é necessário enviar comandos pela UART. Na
instalação registrada, a UART permaneceu recebendo logs para observação;
a instalação com gabinete sempre fechado, sem essa observação, não foi
repetida separadamente.

## Antes de começar

É necessário ter:

- EX511 **V2** com o [layout de 17 partições](hardware.md), stock ativo no
  slot0 e rootfs_1 sem associação UBI. Outro layout/slot ativo exige análise;
  não adapte números de MTD ou comandos do AX55.
- Acesso SSH ao stock com **UID efetivo 0**. O usuário era admin no aparelho
  testado, mas um nome de usuário não comprova privilégios. Este repositório
  não fornece senha, exploit da interface web ou desbloqueio root universal.
- Backups fora do roteador, energia estável, chave SSH conferida e ciência
  dos [limites de recuperação](recovery.md). Preservar stock não garante
  retorno automático se o OpenWrt iniciar e travar depois.
- Linux com Python 3, pexpect e OpenSSH, e imagens compiladas com os dados
  regionais/FEM corretos do seu próprio aparelho.

Durante a instalação, isole o EX511 da rede principal e ligue o computador
à LAN1. A Internet do computador pode vir por outra interface. Não use os
scripts específicos downstream router/ISP deste operador como um instalador genérico.

## 1. Conferir o acesso original e guardar metadados

O IP observado era $EX511_HOST; confirme o endereço do seu aparelho. Obtenha
a chave SSH e confira a impressão digital por um caminho independente antes
de aceitá-la. `ssh-keyscan` sozinho não autentica o dispositivo.

```sh
mkdir -m 700 -p "$HOME/ex511-private"
ssh-keyscan -T 5 $EX511_HOST > "$HOME/ex511-private/stock-candidate.keys"
ssh-keygen -lf "$HOME/ex511-private/stock-candidate.keys"
# Somente depois de identificar e conferir a chave:
cp "$HOME/ex511-private/stock-candidate.keys" "$HOME/ex511-private/stock.keys"
ssh -tt -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$HOME/ex511-private/stock.keys" admin@$EX511_HOST
```

Dentro do shell stock:

```sh
grep '^Uid:' /proc/self/status
uname -a
cat /proc/mtd
cat /proc/cmdline
cat /proc/boot_info/rootfs/primaryboot
cat /proc/boot_info/rootfs/upgradepartition
cat /etc/fw_env.config
fw_printenv bootcmd
fw_printenv tp_boot_idx
fw_printenv config_name
```

O cenário coberto exige UID 0, primaryboot=0, upgradepartition=rootfs_1,
bootcmd=bootipq e tp_boot_idx indefinido. O FIT testado usa config@mp03.3.
Confirme todos os tamanhos/offsets e associações UBI antes de escrever.
Se houver divergência, pare: não remova as verificações para continuar.

No computador, registre a captura privada:

```sh
python3 scripts/ex511-v2/collect-stock-ssh.py \
  --host $EX511_HOST --user admin \
  --known-hosts "$HOME/ex511-private/stock.keys" \
  --output "$HOME/ex511-private/stock-capture"
```

## 2. Fazer backups antes de qualquer alteração

Guarde os dois slots de firmware, APPSBLENV, APPSBL, os dois BOOTCONFIG e os
dados de fábrica/calibração. Se possuir dump completo, registre se inclui
OOB/ECC e como foram tratados blocos ruins. Não publique esses arquivos.

O servidor stock testado recusava `ssh host comando`, mas aceitava uma
sessão de shell. A ferramenta abaixo usa esse caminho para transferir bytes.
Substitua N e BYTES pelos dados **da partição física identificada por nome**:

```sh
python3 scripts/ex511-v2/stock-transfer.py \
  --host $EX511_HOST --user admin \
  --known-hosts "$HOME/ex511-private/stock.keys" \
  get --remote /dev/mtdN --bytes BYTES \
  --output "$HOME/ex511-private/PARTICAO-before.bin"
```

Repita para as partições revisadas. Confira comprimento, SHA256 e uma segunda
leitura independente ou checksum confiável no dispositivo. Uma leitura normal
de MTD não é um dump OOB nem uma receita completa para restaurar NAND.
Confirme o CRC de APPSBLENV com o comando da [etapa 2 do guia técnico](installation-ssh.md#2-private-backups-before-any-write).
O layout observado era uma área de ambiente de 256 KiB dentro de uma partição
de 512 KiB; dois setores não demonstram ambiente redundante.

## 3. Preparar três imagens diferentes

Siga [build-current.md](build-current.md), que contém fonte/feeds fixados,
importação privada do BDF e comandos de validação. Preserve separadamente:

| Etapa | Imagem | Permissão de escrita no kernel |
| --- | --- | --- |
| Diagnóstico | Initramfs do perfil initramfs-test, encapsulado em UBI contendo somente kernel | Nenhuma das 17 partições |
| Persistência protegida | factory.ubi do perfil slot1 | Somente rootfs_1 |
| Controle do padrão de boot | sysupgrade do perfil slot1-env | rootfs_1 e APPSBLENV |

O kernel do diagnóstico é maior que o volume kernel do stock testado.
**Não basta substituir esse volume.** O procedimento formata o slot inativo
inteiro com a UBI adequada. Não confunda FIT, UBI e arquivo sysupgrade.
Um nome factory.ubi não significa que a interface web TP-Link o aceite.

## 4. Testar o mecanismo de boot ainda no stock

Depois dos backups, CRC e conferência do estado original, no shell stock:

```sh
set -e
EXPECTED_WRAPPER='if printenv ex511_trial; then setenv ex511_trial; if saveenv; then setenv tp_boot_idx 0; fi; fi; bootipq'
fw_setenv bootcmd "$EXPECTED_WRAPPER"
[ "$(fw_printenv bootcmd)" = "bootcmd=$EXPECTED_WRAPPER" ] || exit 1
fw_setenv ex511_trial 1
[ "$(fw_printenv ex511_trial)" = 'ex511_trial=1' ] || exit 1
sync
```

Antes de reiniciar, salve uma leitura completa do ambiente armado e confira o CRC; depois execute `reboot` separadamente.


Confira sucesso e leitura exata de cada variável antes de reiniciar. Essa
etapa grava o ambiente, mas não altera o slot de firmware. A alimentação não
pode ser interrompida durante a gravação. Após voltar ao stock, comprove:
primaryboot=0, ex511_trial ausente, tp_boot_idx ausente e ambiente com CRC
válido. Isso testa a remoção persistente da flag antes da seleção em RAM.
Se não corresponder, pare.

## 5. Enviar a UBI de diagnóstico para a RAM

Confira espaço em /tmp e MemAvailable; a etapa histórica exigiu mais de
40 MiB disponíveis. Não envie a imagem para uma partição de flash.

```sh
python3 scripts/ex511-v2/stock-transfer.py \
  --host $EX511_HOST --user admin \
  --known-hosts "$HOME/ex511-private/stock.keys" \
  put --remote /tmp/ex511-install/trial.ubi \
  --input /caminho/absoluto/para/trial.ubi
```

A ferramenta lê os bytes de volta e compara com o arquivo local. Ela não
faz flash, não reinicia e não muda o boot. Só prossiga se a comparação passar.

## 6. Gravar exclusivamente rootfs_1 e conferir a leitura

Reconfirme que stock está no slot0 e rootfs_1 não está associado a UBI.
Os comandos abaixo são **destrutivos para rootfs_1** e só valem para o layout
já conferido. Não execute se algum backup, verificador ou transferência falhou.

```sh
TARGET=$(awk -F '[:"]' '$3 == "rootfs_1" { print $1 }' /proc/mtd)
case "$TARGET" in mtd[0-9]*) ;; *) echo 'PARE: destino indefinido'; exit 1;; esac
[ "$(cat /sys/class/mtd/$TARGET/name)" = rootfs_1 ] || exit 1
[ "$(cat /sys/class/mtd/$TARGET/size)" = 38141952 ] || exit 1
[ "$(cat /sys/class/mtd/$TARGET/offset)" = 57278464 ] || exit 1
[ "$(cat /sys/class/mtd/$TARGET/erasesize)" = 131072 ] || exit 1
[ "$(cat /proc/boot_info/rootfs/primaryboot)" = 0 ] || exit 1
[ "$(cat /proc/boot_info/rootfs/upgradepartition)" = rootfs_1 ] || exit 1
for path in /sys/class/ubi/ubi[0-9]*/mtd_num; do
  [ ! -r "$path" ] || [ "$(cat "$path")" != "${TARGET#mtd}" ] || exit 1
done
ubiformat "/dev/$TARGET" -y -s 2048 -O 2048 -f /tmp/ex511-install/trial.ubi
```

Não formate rootfs, APPSBL, BOOTCONFIG ou dados de fábrica. Guarde o resultado
completo. Se a sessão cair, não repita a gravação supondo que falhou.

Leia rootfs_1 inteiro para o computador e rode check-trial-ubi.py com a leitura
e o FIT original. Exija reconstrução exata do FIT e CRCs válidos. Compare
novamente os hashes de rootfs, APPSBL e ambos BOOTCONFIG com os backups;
eles precisam permanecer iguais. Veja os comandos na [etapa 6 técnica](installation-ssh.md#6-format-only-the-verified-inactive-physical-slot--stock-shell).

## 7. Iniciar o diagnóstico uma única vez

Somente depois de validar a gravação e as partições preservadas:

```sh
set -e
EXPECTED_WRAPPER='if printenv ex511_trial; then setenv ex511_trial; if saveenv; then setenv tp_boot_idx 1; fi; fi; bootipq'
fw_setenv bootcmd "$EXPECTED_WRAPPER"
[ "$(fw_printenv bootcmd)" = "bootcmd=$EXPECTED_WRAPPER" ] || exit 1
fw_setenv ex511_trial 1
[ "$(fw_printenv ex511_trial)" = 'ex511_trial=1' ] || exit 1
sync
```

Antes de reiniciar, salve uma leitura completa do ambiente armado e confira o CRC; depois execute `reboot` separadamente.


No computador isolado, use $PC_SOURCE/24 na Ethernet e acesse o OpenWrt em
$OPENWRT_HOST. Identifique a nova chave SSH, diferente da chave stock, e guarde-a
separadamente. Defina senha forte. Confira placa, versão, Ethernet, MAC,
calibração, memória e que todas as 17 partições estão somente leitura.
Não use sysupgrade nessa imagem de diagnóstico e não desbloqueie MTDs.
Wi-Fi estará desligado por padrão; faça o primeiro acesso por cabo.

Confirme ambiente com CRC válido e sem ex511_trial/tp_boot_idx persistentes.
Execute um reboot controlado e comprove o retorno ao stock slot0 antes de
seguir. O teste inicial é RAM/initramfs; ainda não há overlay persistente.

## 8. Passar para SquashFS/UBIFS, ainda com stock como padrão

Volte ao stock e repita transferência, verificações de slot inativo e
ubiformat, agora com a factory.ubi **protegida do perfil slot1**. Não use o
tar sysupgrade nessa operação. Valide a leitura integral com
check-slot1-image.py, sua imagem sysupgrade correspondente, kernel config
e fwtool. Compare novamente os hashes das partições preservadas.

A wrapper final da etapa 7 precisa permanecer exata. Arme somente
ex511_trial=1, confira, sincronize e reinicie. No OpenWrt comprove:
ubi.mtd=rootfs_1, /rom SquashFS, /overlay UBIFS, somente rootfs_1 gravável e
configurações persistentes. Teste retorno ao stock e uma segunda entrada no
slot1. Persistência da configuração não é o mesmo que OpenWrt como boot padrão.

## 9. Atualizar para slot1-env

Salve configurações fora do aparelho. A RAM é limitada: no teste, os APs e
serviços foram pausados e ath11k_ahb descarregado, liberando cerca de 40 MiB,
com Ethernet funcionando. Não presuma os mesmos módulos/serviços em outra
imagem nem transfira uma imagem grande com memória esgotada.

Envie a sysupgrade validada do perfil slot1-env para /tmp, confira os bytes e
rode no OpenWrt protegido:

```sh
sysupgrade -T /tmp/slot1-env-sysupgrade.bin
# Somente após aceite e conferência de backup/memória/perfil:
sysupgrade -c --no-provisioning /tmp/slot1-env-sysupgrade.bin
```

Essas opções pertencem à versão testada desta branch. Não use -F. A atualização
fica em rootfs_1 e não muda o padrão de boot: haverá retorno ao stock.
Arme novamente um teste pelo stock e confira o novo perfil, configurações,
calibração e somente duas partições graváveis: APPSBLENV e rootfs_1.

## 10. Tornar OpenWrt padrão depois dos testes

O controlador usa SSH BatchMode: primeiro autorize a chave pública do
computador em /etc/dropbear/authorized_keys do OpenWrt (0600, root) e teste
login sem senha com a chave do host conferida. Nunca copie a chave privada.

Use o controlador atual no **computador**, com a chave OpenWrt conferida:

```sh
python3 scripts/ex511-v2/boot-policy.py snapshot \
  --host $OPENWRT_HOST --source $PC_SOURCE \
  --known-hosts /privado/openwrt.keys --output /privado/ambiente-atual.bin
python3 scripts/ex511-v2/boot-policy.py plan \
  --before /privado/ambiente-atual.bin --policy openwrt --output /privado/plano-novo
# Leia plano-novo/plan.json antes de aplicar.
python3 scripts/ex511-v2/boot-policy.py apply \
  --host $OPENWRT_HOST --source $PC_SOURCE \
  --known-hosts /privado/openwrt.keys \
  --reviewed-plan /privado/plano-novo/plan.json --backup-dir /privado/transacao-nova
```

O controlador exige a wrapper exata, marcador DT do perfil, CRC, geometria e
proteções corretos; não aceita qualquer instalação. Nunca reinicia sozinho.
Exija verified.json e leitura completa conferida antes de mandar reboot.
Teste boot padrão, retorno deliberado ao stock com plano novo --policy stock,
e desligar/ligar fisicamente. Não há rollback automático para todo travamento.

## Depois da instalação

Configure suas próprias redes, credenciais, país/canais e firewall. O cenário
ISP/downstream router é um exemplo testado, não um requisito. NSS já fornece aceleração e
distribuição de IRQs; não habilite flow offloading convencional nem instale
irqbalance como ajuste genérico sem medir. Veja [operação e desempenho](network-operation.md).

As próximas atualizações precisam ser específicas para slot1-env, passar nos
verificadores e em sysupgrade -T. Elas atualizam o mesmo slot1, preservando
stock slot0; não constituem atualização A/B automática.
