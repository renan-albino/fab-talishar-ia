import React, { useMemo } from 'react';
import { useAppSelector } from 'app/Hooks';
import { RootState } from 'app/Store';
import styles from './ChessAdvantageTracker.module.css';

export default function ChessAdvantageTracker() {
  const amIPlayerOne = useAppSelector(
    (state: RootState) => state.game.gameInfo.playerID === 1
  );

  const p1 = useAppSelector((state: RootState) => state.game.playerOne);
  const p2 = useAppSelector((state: RootState) => state.game.playerTwo);

  const myPlayer = amIPlayerOne ? p1 : p2;
  const oppPlayer = amIPlayerOne ? p2 : p1;

  const myHealth = Number(myPlayer?.Health ?? 40);
  const oppHealth = Number(oppPlayer?.Health ?? 40);

  const myHandCount = Array.isArray(myPlayer?.Hand) ? myPlayer.Hand.length : 4;
  const oppHandCount = Array.isArray(oppPlayer?.Hand) ? oppPlayer.Hand.length : 4;

  const myArsenalCount = Array.isArray(myPlayer?.Arsenal) ? myPlayer.Arsenal.length : 0;
  const oppArsenalCount = Array.isArray(oppPlayer?.Arsenal) ? oppPlayer.Arsenal.length : 0;

  const myName = String(myPlayer?.Name || 'Você');
  const oppName = String(oppPlayer?.Name || 'Bot AI');

  const { evalScore, myPercent, oppPercent, evalLabel, evalBadgeClass } = useMemo(() => {
    const hpDelta = myHealth - oppHealth;
    const handDelta = myHandCount - oppHandCount;
    const arsDelta = myArsenalCount - oppArsenalCount;

    // Fórmula de Avaliação Posicional Estilo Xadrez FaB
    const score = Number(((hpDelta * 0.4) + (handDelta * 0.9) + (arsDelta * 0.7)).toFixed(1));

    // Sigmoid para converter eval em porcentagem (estilo Chess.com de 5% a 95%)
    let pct = 50 + (score * 4.5);
    if (myHealth <= 0) pct = 0;
    else if (oppHealth <= 0) pct = 100;
    else pct = Math.max(5, Math.min(95, Math.round(pct)));

    const oppPct = 100 - pct;

    let label = '0.0';
    let badgeClass = styles.badgeNeutral;

    if (myHealth <= 0) {
      label = '0-1 (Derrota)';
      badgeClass = styles.badgeOpponent;
    } else if (oppHealth <= 0) {
      label = '1-0 (Vitória)';
      badgeClass = styles.badgePlayer;
    } else if (score > 0.5) {
      label = '+' + score;
      badgeClass = styles.badgePlayer;
    } else if (score < -0.5) {
      label = String(score);
      badgeClass = styles.badgeOpponent;
    } else {
      label = '0.0';
      badgeClass = styles.badgeNeutral;
    }

    return {
      evalScore: score,
      myPercent: pct,
      oppPercent: oppPct,
      evalLabel: label,
      evalBadgeClass: badgeClass
    };
  }, [myHealth, oppHealth, myHandCount, oppHandCount, myArsenalCount, oppArsenalCount]);

  return (
    <div className={styles.trackerContainer}>
      <div className={styles.headerRow}>
        <div className={styles.playerInfoLeft}>
          <span className={styles.playerName}>{myName.substring(0, 12)}</span>
          <span className={styles.hpPill}>{myHealth} HP</span>
        </div>
        <div className={`${styles.evalBadge} ${evalBadgeClass}`} title={`Score Posicional FaB: ${evalScore}`}>
          <span>{evalLabel}</span>
        </div>
        <div className={styles.playerInfoRight}>
          <span className={styles.hpPillOpp}>{oppHealth} HP</span>
          <span className={styles.playerName}>{oppName.substring(0, 12)}</span>
        </div>
      </div>

      <div className={styles.barWrapper}>
        <div
          className={styles.playerBar}
          style={{ width: `${myPercent}%` }}
          title={`${myName}: ${myPercent}% de probabilidade`}
        >
          {myPercent >= 22 && <span className={styles.barPercentText}>{myPercent}%</span>}
        </div>
        <div
          className={styles.oppBar}
          style={{ width: `${oppPercent}%` }}
          title={`${oppName}: ${oppPercent}% de probabilidade`}
        >
          {oppPercent >= 22 && <span className={styles.barPercentText}>{oppPercent}%</span>}
        </div>
      </div>
    </div>
  );
}
