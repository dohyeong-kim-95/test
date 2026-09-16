# GOAL

70bit 이진 최적화를 진행하기 전에 쓸 **채점기**를 만든다.
최적화기를 붙이기 전에, 대리모델(surrogate)이 어디까지 믿을 만한지를 먼저 숫자로 확인하는 것이 목적이다.

- 입력 `X`: 70비트 binary array
- 출력 `Y`: scalar 6개

## 할 일

1. 아주 복잡한 GT 계산식을 하나 만든다 — 결정적(deterministic), 미분불가능점이 많을 것
2. 7000개 데이터를 랜덤샘플링하여 `x`, `y`를 기록한다
3. 7000개 데이터를 기반으로 `x -> y` 계산기를 만든다
4. 계산기 정확도 산출 로직을 개발한다

## 코드 컨벤션

- 파일 하나에 다 모아서 작성
- 한 구역에는 한 기능
- Class는 1개 이하
- List comprehension 사용 가능 / **중첩** list comprehension 사용 불가능
- MVP 원칙 — 필요한 것만

## 사용해볼만한 보간 방식

1. KNN 거리역수가중보간
2. Hamming KNN with exponential kernel
3. Bit intersection model

## 허용 가능

7000점으로 신뢰도를 얻기 힘든 공간은 `untrusted` / `data lack` 정도로 **predict를 거절할 수 있다.**
전 구간을 억지로 예측하는 것보다, 모르는 구간을 모른다고 말하는 쪽이 낫다.
