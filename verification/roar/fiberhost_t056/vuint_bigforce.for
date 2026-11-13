C======================================================================
C     VUINTERACTION_BASELINE + BIG-FORCE LOGGER (fh056 B diagnosis)
C     Same contact law as the baseline routine; additionally writes
C     <outdir>/vuint_big.txt. Run with ONE thread (SAVE counters).
C     Rows:
C       BIG  : d_eff > 20 um, or |incoming stress| > 1e7, or
C              area > 2e-6 m^2 (see header line for columns)
C       CAP  : first-seen point already overclosed (d > 50 um)
C       SUM  : per call with any pressure, or every 500th call
C======================================================================
      SUBROUTINE VUINTERACTION (
     *     STRESS, FLUXSLV, FLUXMST,
     *     STATE, SED,
     *     SFD, SCD, SPD, SVD,
     *     NBLOCK, NBLOCKANAL, NBLOCKEDGE,
     *     NNODSTATE, NNODSLV, NNODMST, NDIR,
     *     NSTATES, NPROPS, NTEMP, NFIELDS,
     *     JFLAGS, RDATA,
     *     SURFINT, SURFSLV, SURFMST,
     *     JSLVUID, JMSTUID, PROPS,
     *     PENETRATION, DRDISP, DROT, DIRCOS, STIFFDEF, CONDUCTDEF,
     *     COORDSLV, COORDMST, AREAPROX, SHAPESLV, SHAPEMST,
     *     TEMPSLV, TEMPMST, DTEMPSLV, DTEMPMST,
     *     FIELDSLV, FIELDMST, DFIELDSLV, DFIELDMST )
C
      INCLUDE 'vaba_param.inc'
C
      CHARACTER*80 SURFINT, SURFSLV, SURFMST
      DIMENSION JFLAGS(*), RDATA(*)
      DIMENSION JSLVUID(NNODSLV, NBLOCK), JMSTUID(NNODMST, NBLOCK)
      DIMENSION PROPS(NPROPS)
      DIMENSION PENETRATION(NBLOCK), DRDISP(NDIR, NBLOCK)
      DIMENSION DROT(2, 2, NBLOCK), DIRCOS(NDIR, NDIR, NBLOCK)
      DIMENSION STIFFDEF(NBLOCK), CONDUCTDEF(NBLOCK)
      DIMENSION COORDSLV(NDIR, NNODSLV, NBLOCK), COORDMST(NDIR, NBLOCK)
      DIMENSION AREAPROX(NBLOCK)
      DIMENSION TEMPSLV(NBLOCK), TEMPMST(NBLOCK)
      DIMENSION DTEMPSLV(NBLOCK), DTEMPMST(NBLOCK)
      DIMENSION FIELDSLV(NFIELDS, NBLOCK), FIELDMST(NFIELDS, NBLOCK)
      DIMENSION DFIELDSLV(NFIELDS, NBLOCK), DFIELDMST(NFIELDS, NBLOCK)
      DIMENSION STRESS(NDIR, NBLOCK), FLUXSLV(NBLOCK), FLUXMST(NBLOCK)
      DIMENSION STATE(NSTATES, NNODSTATE, NBLOCK)
      DIMENSION SED(NBLOCK), SFD(NBLOCK), SCD(NBLOCK), SPD(NBLOCK),
     *          SVD(NBLOCK)
C
      INTEGER K, IDIR, J, IU, LENOUT, NCALL, NPRT, IFIRST
      REAL*8 D, D_POS, D0, D_EFF, PRESS, KPEN, FRIC, KS
      REAL*8 DS1, DS2, TAU1, TAU2, TAU_MAG, TAU_CRIT, SCALE
      REAL*8 S1IN, ST1IN, ST2IN, FMAX, DMAX, AMAX, FRC
      LOGICAL LOPEN
      CHARACTER*256 OUTDIR
      SAVE NCALL, NPRT, LOPEN
      DATA NCALL /0/, NPRT /0/, LOPEN /.FALSE./
C
      IU = 118
      NCALL = NCALL + 1
      IF (.NOT. LOPEN) THEN
        CALL VGETOUTDIR(OUTDIR, LENOUT)
        OPEN(UNIT=IU, FILE=OUTDIR(1:LENOUT)//'/vuint_big.txt',
     *       STATUS='UNKNOWN')
        LOPEN = .TRUE.
        WRITE(IU,'(A)') '# BIG|CAP call k slvuid mst1..4 d d0 '//
     *   'st1in st2in area press force s1in s2out xs ys zs '//
     *   'xm ym zm n1 n2 n3 stiffdef'
        WRITE(IU,'(A)') '# SUM call nblock nnodstate nnodmst '//
     *   'jflag1 jflag2 dmax fmax amax rdata1..4'
      END IF
      FMAX = 0.0D0
      DMAX = -1.0D30
      AMAX = 0.0D0
C
      DO K = 1, NBLOCK
        IF (NPROPS .GE. 1 .AND. PROPS(1) .GT. 0.0D0) THEN
          KPEN = PROPS(1)
        ELSE IF (STIFFDEF(K) .GT. 0.0D0) THEN
          KPEN = STIFFDEF(K)
        ELSE
          KPEN = 1.0D11
        END IF
        IF (NPROPS .GE. 2) THEN
          FRIC = PROPS(2)
        ELSE
          FRIC = 0.01D0
        END IF
C
        D = PENETRATION(K)
        D_POS = MAX(D, 0.0D0)
        S1IN = STRESS(1, K)
        ST1IN = STATE(1, 1, K)
        ST2IN = STATE(2, 1, K)
        IFIRST = 0
        IF (STATE(2, 1, K) .LT. 0.5D0) THEN
          IFIRST = 1
          D0 = D_POS
          STATE(1, 1, K) = D0
          STATE(2, 1, K) = 1.0D0
        ELSE
          D0 = STATE(1, 1, K)
          D0 = MIN(D0, D_POS)
          STATE(1, 1, K) = D0
        END IF
        D_EFF = MAX(0.0D0, D - D0)
        PRESS = KPEN * D_EFF
        STRESS(1, K) = PRESS
C
        IF (FRIC .GT. 0.0D0 .AND. PRESS .GT. 0.0D0) THEN
          DS1 = DRDISP(2, K)
          DS2 = 0.0D0
          IF (NDIR .GE. 3) DS2 = DRDISP(3, K)
          KS = KPEN
          TAU1 = STRESS(2, K) - KS * DS1
          TAU2 = 0.0D0
          IF (NDIR .GE. 3) TAU2 = STRESS(3, K) - KS * DS2
          TAU_MAG = SQRT(TAU1*TAU1 + TAU2*TAU2)
          TAU_CRIT = FRIC * PRESS
          IF (TAU_MAG .GT. TAU_CRIT .AND. TAU_MAG .GT. 1.0D-14) THEN
            SCALE = TAU_CRIT / TAU_MAG
            STRESS(2, K) = TAU1 * SCALE
            IF (NDIR .GE. 3) STRESS(3, K) = TAU2 * SCALE
          ELSE
            STRESS(2, K) = TAU1
            IF (NDIR .GE. 3) STRESS(3, K) = TAU2
          END IF
        ELSE
          DO IDIR = 2, NDIR
            STRESS(IDIR, K) = 0.0D0
          END DO
        END IF
C
        FRC = PRESS * AREAPROX(K)
        FMAX = MAX(FMAX, FRC)
        DMAX = MAX(DMAX, D)
        AMAX = MAX(AMAX, AREAPROX(K))
        IF (NPRT .LT. 3000000) THEN
          IF (D_EFF .GT. 2.0D-5 .OR. ABS(S1IN) .GT. 1.0D7 .OR.
     *        AREAPROX(K) .GT. 2.0D-6) THEN
            NPRT = NPRT + 1
            WRITE(IU,'(A,2I8,I10,4I10,18ES12.4)') 'BIG ', NCALL, K,
     *        JSLVUID(1,K), (JMSTUID(J,K), J=1,MIN(NNODMST,4)),
     *        (0, J=MIN(NNODMST,4)+1,4),
     *        D, D0, ST1IN, ST2IN, AREAPROX(K), PRESS, FRC, S1IN,
     *        STRESS(2,K), COORDSLV(1,1,K), COORDSLV(2,1,K),
     *        COORDSLV(3,1,K), COORDMST(1,K), COORDMST(2,K),
     *        COORDMST(3,K), DIRCOS(1,1,K), DIRCOS(2,1,K),
     *        DIRCOS(3,1,K)
          ELSE IF (IFIRST .EQ. 1 .AND. D .GT. 5.0D-5) THEN
            NPRT = NPRT + 1
            WRITE(IU,'(A,2I8,I10,4I10,18ES12.4)') 'CAP ', NCALL, K,
     *        JSLVUID(1,K), (JMSTUID(J,K), J=1,MIN(NNODMST,4)),
     *        (0, J=MIN(NNODMST,4)+1,4),
     *        D, D0, ST1IN, ST2IN, AREAPROX(K), PRESS, FRC, S1IN,
     *        STRESS(2,K), COORDSLV(1,1,K), COORDSLV(2,1,K),
     *        COORDSLV(3,1,K), COORDMST(1,K), COORDMST(2,K),
     *        COORDMST(3,K), DIRCOS(1,1,K), DIRCOS(2,1,K),
     *        DIRCOS(3,1,K)
          END IF
        END IF
C
        SED(K) = 0.5D0 * PRESS * D_EFF
        SFD(K) = 0.0D0
        SCD(K) = 0.0D0
        SPD(K) = 0.0D0
        SVD(K) = 0.0D0
        FLUXSLV(K) = 0.0D0
        FLUXMST(K) = 0.0D0
      END DO
C
      IF (FMAX .GT. 0.0D0 .OR. MOD(NCALL, 500) .EQ. 0) THEN
        WRITE(IU,'(A,I9,5I8,7ES12.4)') 'SUM ', NCALL, NBLOCK,
     *    NNODSTATE, NNODMST, JFLAGS(1), JFLAGS(2), DMAX, FMAX, AMAX,
     *    RDATA(1), RDATA(2), RDATA(3), RDATA(4)
      END IF
      IF (MOD(NCALL, 200) .EQ. 0) CALL FLUSH(IU)
C
      RETURN
      END
