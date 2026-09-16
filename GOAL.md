# GOAL

70bit 이진 최적화를 진행하기 전, 채점기를 만들고 싶어요. X-> binary array Y: scalar 6개
1. 특정 아주 복잡한 GT계산식(결정적,미분불가능점많음) 을 하나 만들기
2. 7000개 데이터 랜덤샘플링하여 x,y 기록
3. 7000개 데이터를 기반으로 x->y계산기 만들기
4. 계산기 정확도 산출로직 개발

[코드컨벤션]
파일 하나에 다 모아서 작성
한 구역에는 한 기능
Class는 1개 이하
List comprehension 사용 가능
중첨 list comprehension 사용 불가능

[사용해볼만한 보간방식]
1. Knn 거리역수가중보간
2. Hamming knn with exponential kernel
3. bit intersection model

[허용 가능]
7000점으로 신뢰도를 얻기 힘든 공간을 untrusted/data lack 정도로 predict 거절할 수 있음
