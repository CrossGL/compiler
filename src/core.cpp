#include <iostream>
#include "../headers/lexer.h"

int main(){
    Lexer lex("x<<3;x>>3;x<=3;x=3.2;x>=3;x==5;x!=2;x&&2;x||20;x~20;x--;Shader main{position = vec3(1,1,2);}");
    std::vector<Token> types = lex.getTokens();

    std::cout<<"size of the tokens: "<<types.size()<<std::endl;
    for(auto it: types){
        std::cout<<it.value<<" ";
    }
    std::cout<<"\n";
    return 0;
}