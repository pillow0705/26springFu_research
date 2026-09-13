# Type I(6)：全实六次乘法的简单复六维阿贝尔簇

**agent:** S4 (math4)  
**subproblem:** Type I(6) 的 Hodge 群、极化及 (B^p,D^p,E^p)  ���数  
**version:** v1.0  
**status:** proof draft complete, subject to committee review

## 0. 设定与结论

设 (A/mathbf C) 是简单的六维阿贝尔簇，且是 Albert Type I：
\[
  D=\operatorname {End}^0(A)=F,
  \qquad [F:\mathbf Q]=6,
\]
其中 (F) 是全实域。令 (V=H^1(A,mathbf Q))，并令
\[
 B^p(A)=H^{2p}(A,mathbf Q)\cap H^{p,p}(A),
 \quad D^*(A)=\mathbf Q[B^1(A)],
 \quad E^p(A)=B^p(A)/D^p(A).
\]

**主结论。** 有
\[
 \dim_FV=2,
 \qquad \operatorname{Hg}(A)=L(A)
   =\operatorname{Res}_{F/\mathbf Q}\operatorname{SL}_{2,F},
\]
其中 (L(A)) 是由极化定义的 Lefschetz 群。对 (0\leq p\leq6)，
\[
 B^p(A)=D^p(A),\qquad
 \dim_{mathbf Q}B^p(A)=\dim_{mathbf Q}D^p(A)=\binom 6p,
 \qquad E^p(A)=0.
\]
在其它次数 (B^p=D^p=0)。因此 Type I(6) 中没有异常 Hodge 类，且 (A) 的 Hodge 猜想成立。

## 1. 依据与标准事实

本文使用如下标准结果。

1. 对复阿贝尔簇，Mumford 的固定张量描述给出
   \[
   \operatorname{End}_{\operatorname{Hg}(A)}H^1(A,\mathbf Q)
       =\operatorname{End}^0(A),
   \qquad
   B^p(A)=\left(\bigwedge^{2p}V\right)^{\operatorname{Hg}(A)}.
   \]
   该表述及其记号见 Hazama, Proposition 2.1。
2. 当 (operatorname{End}^0(A)) 的中心是全实域（更一般地是全实域的乘积）时，
   (operatorname{Hg}(A)) 是半单群；见 Hazama, Proposition 2.2（归于 Tankeev）。
3. Hazama 的 Type I 计算表明：若 (A_1) 是 Type I 且
   (operatorname{End}^0(A_1)=F_1) 为全实域，则
   (operatorname{Hg}(A_1)=operatorname{SL}_2(F_1))（见其文末 Remark，
   这里的 (operatorname{SL}_2(F_1)) 是 (operatorname{Res}_{F_1/\mathbf Q}operatorname{SL}_2) 的简写）。
   下文给出本六维情形的直接 Lie 代数证明，因此不把该 Remark 当作黑箱。
4. Lefschetz ((1,1)) 定理说明 (B^1(A)=\operatorname{NS}(A)_{\mathbf Q})，故除子类是代数的。

主要参考：

* F. Hazama, *Algebraic cycles on abelian varieties with many real endomorphisms*,
  Tohoku Math. J. **35** (1983), 303--308,
  https://www.jstage.jst.go.jp/article/tmj1949/35/2/35_2_303/_pdf/-char/en 。
* B. J. J. Moonen--Y. G. Zarhin, *Weil classes on abelian varieties*,
  alg-geom/9612017，尤其是其 Hodge 判别准则，
  https://arxiv.org/abs/alg-geom/9612017 。

## 2. 维数约束与极化

由 (dim_{mathbf Q}V=2dim A=12) 及 ([F:mathbf Q]=6)，得
\[
  \dim_FV=12/6=2. 
\]
Type I 的 Rosati 对合限制在 (F) 上为恒等。取一个极化的 Riemann 形式
(psi)。由于
\[
 \psi(av,w)=\psi(v,a^\dagger w)=\psi(v,aw)\quad(a\in F),
\]
(psi) 是 (F)-平衡的。选取 (F)-基后，它可写成
\[
 \psi((x_1,y_1),(x_2,y_2))
  =\operatorname{Tr}_{F/\mathbf Q}
       \bigl(\alpha(x_1y_2-y_1x_2)\bigr),
 \tag{2.1}
\]
其中 (alphain F^\times) 在六个实嵌入下均为正（若改变交替形式的符号，
“正”相应作一致的符号约定）。因此在有理层面极化锥由
\[
 F_{\mathbf R}^{>0}=\{\alpha\in F\otimes\mathbf R:
                         \sigma(\alpha)>0	ext{ 对所有 }\sigma:F\hookrightarrow\mathbf R\}
\]
给出。固定积分格 (Lambda=H_1(A,mathbf Z)) 后，还须加上
(psi(\Lambda,\Lambda)\subset\mathbf Z)；这一步决定具体的积分极化类型。

由 (2.1)，(F)-线性且保持 (psi) 的群满足
\[
 L(A)(R)=\{g\in\operatorname{GL}_F(V\otimes R):
              \psi(gv,gw)=\psi(v,w)\}
        =\operatorname{SL}_2(F\otimes R).
\]
故
\[
 L(A)=\operatorname{Res}_{F/\mathbf Q}\operatorname{SL}_{2,F}.
 \tag{2.2}
\]
若使用 similitude 群，则
\[
 \operatorname{GSp}_F(V,\psi)(R)
 =\{g\in\operatorname{Res}_{F/\mathbf Q}\operatorname{GL}_2(R):
       \det_F(g)\in R^\times\text{ 来自 }\mathbf G_m(R)\},
 \tag{2.3}
\]
即 (mathbf G_m\cdotoperatorname{Res}_{F/\mathbf Q}operatorname{SL}_2)。
相应的 Hodge 群是其 multiplier 为 (1) 的部分。

## 3. Hodge 群的证明

将标量扩张到 (mathbf C)。六个实嵌入记为
(sigma_1,ldots,sigma_6)，则
\[
 F\otimes_{\mathbf Q}\mathbf C=\prod_{i=1}^6\mathbf C,
 \qquad
 V_{\mathbf C}=\bigoplus_{i=1}^6V_i,
\]
其中 (V_i) 是对应 (sigma_i) 的 (F)-特征空间。

### 引理 3.1
(\dim_{\mathbf C}V_i=2)，且极化形式在每个 (V_i) 上非退化。

**证明。** 若 (vin V_i,win V_j)，则对任意 (ain F)，
\[
 (\sigma_i(a)-\sigma_j(a))\psi(v,w)=0.
\]
当 (i\ne j) 时可选 (a) 使两嵌入值不同，故 (V_i\perp V_j)。
总的 (psi) 非退化，因而其在各 (V_i) 上均非退化。它是交替形式，
所以每个 (dim V_i) 为正偶数；而总维数为 (12)，共有六个非零分量，
遂每个维数都是 (2)。(square)

令 (mathfrak h=\operatorname{Lie}(\operatorname{Hg}(A)_{\mathbf C}))。由 §1 的固定端omorphism
结果，
\[
 \operatorname{End}_{\mathfrak h}(V_{\mathbf C})
   =F\otimes_{\mathbf Q}\mathbf C=\mathbf C^6.
 \tag{3.1}
\]
因此六个 (V_i) 是两两不等价且各自不可约的 (mathfrak h)-模：否则在某一
分量内会出现非标量自同态，或在两个等价分量间出现非零交叉同态，均与 (3.1) 矛盾。

由 Tankeev--Hazama 的半单性结果，(mathfrak h) 半单；由极化，
\[
 \mathfrak h\subseteqigoplus_{i=1}^6mathfrak{sp}(V_i)
       =\bigoplus_{i=1}^6mathfrak{sl}(V_i)
       \simeq\mathfrak{sl}_2^6.
 \tag{3.2}
\]
每个投影 (mathfrak h\tomathfrak{sl}(V_i)) 非零：Hodge 结构在 (V_i) 上的
((1,0)) 与 ((0,1)) 部分各为一维（实嵌入由复共轭固定），所以 Hodge 圆在
(V_i) 上非平凡。因 (mathfrak{sl}_2) 简单，半单像只能是全体
(mathfrak{sl}(V_i))。

对 (i\ne j)，考虑二元投影

\[
 \mathfrak h_{ij}\subseteq\mathfrak{sl}(V_i)\oplus\mathfrak{sl}(V_j).
\]
两个投影均满。由半单 Lie 代数的 Goursat 引理，(mathfrak h_{ij}) 要么是直积，
要么是两个 (mathfrak{sl}_2) 之间某个自同构的图。后一种情形会使 (V_i,V_j)
作为 (mathfrak h)-模等价，违反 (3.1)，故
\[
 \mathfrak h_{ij}=\mathfrak{sl}_2\oplus\mathfrak{sl}_2.
\]
对六个简单因子逐对应用同一 Goursat/子直积论证，得到
\[
 \mathfrak h=\mathfrak{sl}_2^6.
 \tag{3.3}
\]
由于 (operatorname{Hg}(A)) 与 (L(A)) 都是连通群，(3.2)--(3.3) 给出
\[
 \boxed{\operatorname{Hg}(A)=L(A)=\operatorname{Res}_{F/\mathbf Q}\operatorname{SL}_2.}
\]

## 4. Hodge 类的计算

在 (mathbf C) 上，(V_i) 是第 (i) 个 (operatorname{SL}_2) 的标准模，
其余五个因子平凡作用。因此
\[
 \bigwedge^kV_{\mathbf C}
 =\bigoplus_{k_1+\cdots+k_6=k}
      \bigotimes_{i=1}^6\bigwedge^{k_i}V_i.
 \tag{4.1}
\]
单个标准二维 (operatorname{SL}_2)-模的不变量只有
\[
 (\wedge^0V_i)^{\operatorname{SL}_2}=\mathbf C,
 \quad (\wedge^1V_i)^{\operatorname{SL}_2}=0,
 \quad (\wedge^2V_i)^{\operatorname{SL}_2}=\mathbf C.
\]
故 (4.1) 中只有 (k_i\in\{0,2\}) 的项贡献不变量。结合固定张量公式，
\[
 B^p(A)\otimes_{\mathbf Q}\mathbf C
 =\left(\wedge^{2p}V_{\mathbf C}\right)^{\operatorname{Hg}(A)_{\mathbf C}}
 =\bigoplus_{|I|=p}\bigotimes_{i\in I}\wedge^2V_i,
 \tag{4.2}
\]
其中 (I\subset\{1,ldots,6\})。因此
\[
 \boxed{\dim_{\mathbf Q}B^p(A)=\binom 6p\quad(0\le p\le6).}
 \tag{4.3}
\]

特别地，
\[
 \dim B^p: 1,6,15,20,15,6,1
 \quad(p=0,1,2,3,4,5,6).
\]

## 5. 除子代数与异常商

由 (p=1) 的 (4.2)，(B^1_{\mathbf C}) 是六条直线
(wedge^2V_i) 的直和，故 (dim B^1=6)。这也与
\[
 B^1(A)=\operatorname{NS}(A)_{\mathbf Q}
 \simeq \operatorname{End}^0(A)^{\dagger=1}=F
\]
一致。

令 (delta_i) 表示 (wedge^2V_i) 这条线的生成元。则
\[
 \delta_i^2=0,
 \qquad
 \delta_{i_1}\cdots\delta_{i_p}
 \quad(i_1<\cdots<i_p)
\]
正好给出 (4.2) 的各个直和分量，因而构成 (D^p(A)_{\mathbf C}) 的一组基。
所以
\[
 \boxed{D^p(A)=B^p(A),\qquad \dim D^p(A)=\binom6p.}
 \tag{5.1}
\]
从而
\[
 \boxed{E^p(A)=0\quad(0\le p\le6).}
 \tag{5.2}
\]
由于 (B^1) 中每个类由 Lefschetz ((1,1)) 定理是代数类，(5.1) 还证明了
所有 (B^p(A)) 都是代数的；这正是该分支的 Hodge 猜想结论。

## 6. Weil 类核对

对 (F\subset\operatorname{End}^0(A))，Moonen--Zarhin 的 Weil 空间为
\[
 W_F=\bigwedge_F^2V\subset H^2(A,\mathbf Q).
\]
这里 (F) 为全实域，所以每个复嵌入满足 (sigma=\bar\sigma)，且
(dim V^{1,0}_\sigma=dim V^{0,1}_\sigma=1)。其 Hodge 判别准则给出
(W_F) 全部是 Hodge 类。事实上直接由分解可见
\[
 (W_F)_{\mathbf C}=\bigoplus_{i=1}^6\wedge^2V_i=(B^1(A))_{\mathbf C},
 \qquad W_F=B^1(A)=D^1(A).
\]
所以这里的 Weil 空间并不产生异常类。又因为 (operatorname{End}^0(A)=F) 不含
虚二次子域，通常意义上不存在由虚二次乘法产生的 Weil 异常类；(5.2) 更强地
排除了任何其它异常类。

## 7. 维数表

| (p) | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---:|---:|---:|---:|---:|---:|---:|
| (dim_{mathbf Q}B^p(A)) | 1 | 6 | 15 | 20 | 15 | 6 | 1 |
| (dim_{mathbf Q}D^p(A)) | 1 | 6 | 15 | 20 | 15 | 6 | 1 |
| (dim_{mathbf Q}E^p(A)) | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Poincare 对偶 (B^p\simeq B^{6-p}) 与表中对称性一致。

## 8. 未决事项与适用范围

1. 本证明把“Type I(6)”严格解释为
   (operatorname{End}^0(A)=F) 且 (F) 是六次全实域。若题目只给出一个
   (F\hookrightarrowoperatorname{End}^0(A)) 而不排除更大的端omorphism代数，
   则不能直接使用本结论；需另按 Albert 类型重新分支。
2. 上述分类是有理 Hodge 分类。给定积分格 (Lambda) 后，具体积分极化的
   类型还依赖于 (operatorname{End}(A)) 的阶、(Lambda) 作为该阶模的理想类以及
   (2.1) 的整性条件；这些数据不由 (F) 的抽象域结构单独决定，本文不声称完成
   该积分算术分类。
3. 这里没有额外假设 (F/\mathbf Q) Galois；六个嵌入只用于在 (mathbf C) 上
   计算，结论通过 descent 回到 (mathbf Q)。

