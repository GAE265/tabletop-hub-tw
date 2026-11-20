#!/bin/sh
# PROTOTYPE for ticket 07 (throwaway): fake table chatter through the Mac speaker, using the
# built-in zh_TW voice "Meijia", so no real person's voice is sent to the model.
# Usage: sh .scratch/host/prototypes/listen-test/chatter.sh [rounds] [gap_seconds]
rounds=${1:-2}
gap=${2:-5}
i=0
while [ "$i" -lt "$rounds" ]; do
  for line in "我覺得三號一定是血刃，他剛剛出牌出太快了。" "嗯嗯。" "等一下要不要點飲料？我想喝紅茶。" "OK，OK。" "你手上還有水晶嗎？" "哈哈哈，好啦好啦。"; do
    echo "旁人：$line"
    say -v Meijia "$line"
    sleep "$gap"
  done
  i=$((i + 1))
done
