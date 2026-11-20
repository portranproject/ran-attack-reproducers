# 계보와 기여

- 연구·공개 구현 근거: 5G-Spector 논문과 공개 저장소
  - https://github.com/5GSEC/5G-Spector/tree/63e94b9ad8860298894ed7a94e52f00faea02719
  - https://www.csl.sri.com/users/gehani/papers/NDSS-2024.5G-Spector.pdf
- 차용: 공격 코드를 가져오지 않고 GUTI 연결→IdentityRequest 관측 계약만 재작성했다.
- 자체 구현: threshold-bound control, emulation sequence, 가명화, replay·판정·봉인
- 한계: 실제 IMSI/SUPI 노출과 RF 원인은 미관측
